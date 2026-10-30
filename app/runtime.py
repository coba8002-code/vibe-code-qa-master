"""Opt-in, bounded tests in Docker; no host-side project execution."""
import json
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path


_lock = threading.Lock()
_projects = {}
_jobs = {}
_running = set()
MAX_RUNTIME = 600
MAX_OUTPUT = 12_000
IMAGES = {"python": "python:3.12-slim", "node": "node:22-alpine"}
RECIPES = {
    "python": ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
    "node": ["node", "--test"],
}


def register(folder: str):
    directory = Path(folder).expanduser().resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("프로젝트 폴더가 아닙니다")
    if not ((directory / "pyproject.toml").exists() or (directory / "requirements.txt").exists()
            or (directory / "package.json").exists()):
        raise ValueError("Python 또는 Node 프로젝트 설정 파일이 없습니다")
    project_type = "python" if ((directory / "pyproject.toml").exists() or
                                (directory / "requirements.txt").exists()) else "node"
    project_id = uuid.uuid4().hex
    with _lock:
        _projects[project_id] = {"path": str(directory), "name": directory.name, "type": project_type}
    return {"id": project_id, "name": directory.name, "type": project_type}


def projects():
    with _lock:
        return [{"id": key, "name": value["name"], "type": value["type"]}
                for key, value in _projects.items()]


def project_details(project_id):
    with _lock:
        if project_id not in _projects:
            raise ValueError('PC에서 프로젝트 폴더를 먼저 승인하세요')
        return dict(_projects[project_id])


def jobs():
    with _lock:
        return [dict(item) for item in reversed(list(_jobs.values()))]


def _update(job_id, **values):
    with _lock:
        _jobs[job_id].update(values)


def _parse_percent(value):
    try:
        return float(re.sub(r"[^0-9.]", "", value.split("%")[0]))
    except (TypeError, ValueError):
        return 0.0


def _parse_bytes(value):
    match = re.match(r"\s*([\d.]+)\s*([kKmMgGtT]?i?[bB])", value or "")
    if not match:
        return 0
    unit = match.group(2).lower()
    power = {"b": 0, "kb": 1, "kib": 1, "mb": 2, "mib": 2,
             "gb": 3, "gib": 3, "tb": 4, "tib": 4}[unit]
    return int(float(match.group(1)) * (1024 ** power))


def _sample(container_name):
    result = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}", container_name],
                            capture_output=True, text=True, timeout=5, check=False)
    if result.returncode:
        return None
    data = json.loads(result.stdout.splitlines()[0])
    return {"cpu_percent": _parse_percent(data.get("CPUPerc", "0%")),
            "memory_bytes": _parse_bytes(data.get("MemUsage", "0B").split("/")[0])}


def _docker_available(project_type):
    if not shutil.which("docker"):
        return False, "Docker Desktop이 설치되지 않았습니다"
    try:
        result = subprocess.run(["docker", "image", "inspect", IMAGES[project_type]],
                                capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False, "Docker 엔진에 연결할 수 없습니다"
    if result.returncode:
        return False, f"테스트 이미지 {IMAGES[project_type]}가 로컬에 없습니다 (자동 다운로드 안 함)"
    return True, ""


def start(project_id: str, mode: str, duration: int, confirmed: bool):
    if not confirmed:
        raise ValueError("실행 검사 승인 확인이 필요합니다")
    if mode not in {"functional", "soak"}:
        raise ValueError("검사 종류가 유효하지 않습니다")
    if not (5 <= duration <= MAX_RUNTIME):
        raise ValueError("검사 제한 시간은 5~600초입니다")
    with _lock:
        project = _projects.get(project_id)
        if not project:
            raise ValueError("PC에서 프로젝트 폴더를 먼저 승인하세요")
        if _running:
            raise ValueError("실행 검사는 한 번에 하나만 진행할 수 있습니다")
        job_id = uuid.uuid4().hex
        _jobs[job_id] = {"id": job_id, "project": project["name"], "mode": mode,
                         "state": "queued", "cpu_peak_percent": 0, "ram_peak_mb": 0,
                         "runtime_seconds": 0, "cycles": 0, "output": "", "exit_code": None,
                         "note": "실행 중 테스트 컨테이너 리소스만 측정; 메모리 누수 판정은 추세 참고용"}
        _running.add(job_id)
    thread = threading.Thread(target=_run, args=(job_id, project, duration), daemon=True)
    thread.start()
    return dict(_jobs[job_id])


def _run(job_id, project, duration):
    _update(job_id, state="running")
    okay, reason = _docker_available(project["type"])
    if not okay:
        _update(job_id, state="blocked", output=reason)
        with _lock:
            _running.discard(job_id)
        return
    start_time = time.monotonic()
    cycles = 0
    cpu_peak = 0.0
    memory_peak = 0
    memory_samples = []
    output = []
    exit_code = None
    timed_out = False
    try:
        while True:
            elapsed = time.monotonic() - start_time
            if elapsed >= duration:
                break
            name = "vibeqa-" + uuid.uuid4().hex[:18]
            directory = project["path"]
            command = ["docker", "run", "--rm", "--name", name, "--network", "none",
                       "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                       "--pids-limit", "64", "--cpus", "1.0", "--memory", "512m",
                       "--memory-swap", "512m", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                       "--tmpfs", "/run:rw,noexec,nosuid,size=8m",
                       "--mount", f"type=bind,source={directory},target=/src,readonly",
                       "--workdir", "/src", "--env", "PYTHONDONTWRITEBYTECODE=1",
                       IMAGES[project["type"]], *RECIPES[project["type"]]]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            chunks = []
            # A dedicated bounded reader prevents deadlocks if a test prints heavily.
            def drain():
                remaining = MAX_OUTPUT
                while True:
                    data = process.stdout.read(4096)
                    if not data:
                        break
                    if remaining > 0:
                        chunks.append(data[:remaining])
                        remaining -= min(remaining, len(data))
            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            while process.poll() is None and time.monotonic() - start_time < duration:
                try:
                    sample = _sample(name)
                    if sample:
                        cpu_peak = max(cpu_peak, sample["cpu_percent"])
                        memory_peak = max(memory_peak, sample["memory_bytes"])
                        if len(memory_samples) < 1000:
                            memory_samples.append(round(sample["memory_bytes"] / (1024 * 1024), 1))
                except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
                    pass
                time.sleep(0.3)
            if process.poll() is None:
                timed_out = True
                # The exact random-name container is the only termination target.
                subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=8, check=False)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            reader.join(timeout=5)
            exit_code = process.returncode
            cycles += 1
            output.append(b"".join(chunks).decode("utf-8", errors="replace")[-1800:])
            if len(output) > 6:
                output.pop(0)
            _update(job_id, cycles=cycles, cpu_peak_percent=round(cpu_peak, 2),
                    ram_peak_mb=round(memory_peak / (1024 * 1024), 1),
                    runtime_seconds=round(time.monotonic() - start_time, 1))
            if exit_code != 0 or _jobs[job_id]["mode"] == "functional":
                break
        output_text = "\n".join(output)[-MAX_OUTPUT:]
        if cycles == 0 or timed_out:
            status = "timed_out"
        elif re.search(r"Ran 0 tests\b|# tests 0\b", output_text):
            # Recent Python versions return nonzero when discovery finds no tests.
            status = "no_tests"
        elif exit_code != 0:
            status = "failed"
        elif not re.search(r"Ran [1-9][0-9]* tests?\b|# tests [1-9][0-9]*\b", output_text):
            status = "no_tests"
        elif _jobs[job_id]["mode"] == "soak" and time.monotonic() - start_time < duration:
            status = "failed"
        else:
            status = "passed"
        trend = None
        if len(memory_samples) >= 8:
            third = len(memory_samples) // 3
            early = sum(memory_samples[:third]) / third
            late = sum(memory_samples[-third:]) / third
            trend = round(late - early, 1)
        _update(job_id, state=status, exit_code=exit_code, output=output_text,
                ram_trend_delta_mb=trend,
                runtime_seconds=round(time.monotonic() - start_time, 1))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        _update(job_id, state="failed", output=f"테스트 실행 환경 오류: {type(exc).__name__}")
    finally:
        with _lock:
            _running.discard(job_id)
