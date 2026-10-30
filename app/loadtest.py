"""Small opt-in GET-only loopback probe, not an Internet load generator."""
import http.client
import statistics
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

_jobs = {}
_lock = threading.Lock()
_active = False


def _validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("로컬 TEST 서버(http://127.0.0.1) 주소만 허용됩니다")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("인증정보 또는 fragment는 사용할 수 없습니다")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("포트가 유효하지 않습니다") from exc
    if port is None or not (1024 <= port <= 65535):
        raise ValueError("1024~65535 포트를 지정하세요")
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return port, path


def jobs():
    with _lock:
        return [dict(row) for row in reversed(list(_jobs.values()))]


def start(url: str, requests: int, concurrency: int, confirmed: bool):
    global _active
    if not confirmed:
        raise ValueError("로컬 테스트 대상과 부하를 명시적으로 승인해야 합니다")
    if not (1 <= requests <= 100) or not (1 <= concurrency <= 4):
        raise ValueError("요청 최대 100회, 동시 실행 최대 4개")
    port, path = _validate_url(url)
    with _lock:
        if _active:
            raise ValueError("부하 테스트가 이미 실행 중입니다")
        _active = True
        job_id = uuid.uuid4().hex
        _jobs[job_id] = {"id": job_id, "target": f"http://127.0.0.1:{port}{path}",
                         "state": "queued", "requests": requests, "completed": 0,
                         "errors": 0, "p50_ms": None, "p95_ms": None,
                         "note": "로컬 GET 요청만 사용. 인증·쓰기·실서비스 트래픽 미검증"}
    threading.Thread(target=_run, args=(job_id, port, path, requests, concurrency), daemon=True).start()
    return dict(_jobs[job_id])


def _run(job_id, port, path, requests, concurrency):
    global _active
    times = []
    errors = 0

    def request(_):
        start = time.monotonic()
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            connection.request("GET", path, headers={"User-Agent": "vibe-qa-load-probe"})
            response = connection.getresponse()
            response.read(64 * 1024)
            success = 200 <= response.status < 400
        except (OSError, http.client.HTTPException):
            success = False
        finally:
            connection.close()
        return round((time.monotonic() - start) * 1000, 1), success

    try:
        with _lock:
            _jobs[job_id]["state"] = "running"
        # Capped worker count and total requests; does not follow redirects.
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            for index, (latency, okay) in enumerate(executor.map(request, range(requests)), 1):
                times.append(latency)
                errors += int(not okay)
                if index % 5 == 0 or index == requests:
                    with _lock:
                        _jobs[job_id].update(completed=index, errors=errors)
        ordered = sorted(times)
        with _lock:
            _jobs[job_id].update(
                state="failed" if errors else "passed", errors=errors,
                completed=len(times), p50_ms=round(statistics.median(times), 1),
                p95_ms=ordered[max(0, int(len(ordered) * 0.95 + 0.9999) - 1)])
    except Exception:
        with _lock:
            _jobs[job_id].update(state="failed", note="부하 검사 실행 오류")
    finally:
        with _lock:
            _active = False
