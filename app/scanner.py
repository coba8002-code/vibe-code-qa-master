"""Read-only, bounded first-pass source inspection. Never executes project code."""
import re
from pathlib import PurePosixPath

MAX_FILES = 1500
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 24 * 1024 * 1024
EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml",
              ".toml", ".env", ".sh", ".sql", ".html", ".xml", ".kt", ".java"}
NAMES = {"Dockerfile", "requirements.txt", "package.json", "pyproject.toml",
         "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "go.mod",
         "Cargo.toml", "Gemfile", "pom.xml", "build.gradle", "build.gradle.kts"}
EXCLUDE = {"node_modules", ".git", ".venv", "venv", "dist", "build", ".next", "coverage"}

RULES = (
    ("SEC001", "high", "하드코딩된 비밀값 의심",
     re.compile(r"(?i)(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"][A-Za-z0-9_+/-]{16,}['\"]")),
    ("SEC002", "medium", "위험한 동적 코드 실행 패턴",
     re.compile(r"\b(?:eval|exec)\s*\(")),
    ("SEC003", "medium", "취약할 수 있는 셸 실행 방식",
     re.compile(r"(?:shell\s*=\s*True|child_process\.exec\s*\()")),
    ("SEC004", "medium", "TLS 검증 해제 가능성",
     re.compile(r"(?:verify\s*=\s*False|rejectUnauthorized\s*:\s*false)")),
)


def scan(files: list[tuple[str, bytes]], source: str):
    findings = []
    names = []
    scanned = 0
    skipped = 0
    total = 0
    for filename, data in files:
        if len(names) >= MAX_FILES:
            skipped += 1
            continue
        path = PurePosixPath(filename.replace("\\", "/"))
        if ".." in path.parts or path.is_absolute() or any(p in EXCLUDE for p in path.parts):
            skipped += 1
            continue
        if path.suffix.lower() not in EXTENSIONS and path.name not in NAMES:
            skipped += 1
            continue
        if len(data) > MAX_FILE_BYTES or total + len(data) > MAX_TOTAL_BYTES:
            skipped += 1
            continue
        total += len(data)
        scanned += 1
        names.append(str(path))
        text = data.decode("utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for rule_id, severity, title, pattern in RULES:
                if pattern.search(line):
                    findings.append({"rule": rule_id, "severity": severity, "title": title,
                                     "path": str(path), "line": lineno})
                    if len(findings) >= 200:
                        break
            if len(findings) >= 200:
                break
    is_test = any("test" in PurePosixPath(n).name.lower() or "/tests/" in f"/{n}" for n in names)
    has_ci = any(".github/workflows/" in n for n in names)
    has_manifest = any(PurePosixPath(n).name in NAMES for n in names)
    checks = {
        "source_files": "pass" if scanned else "not_run",
        "test_files": "present" if is_test else "missing",
        "github_actions": "present" if has_ci else "missing",
        "dependency_manifest": "present" if has_manifest else "missing",
    }
    return {
        "source": source, "scan_type": "static-first-pass",
        "files_scanned": scanned, "files_skipped": skipped,
        "findings": findings, "checks": checks,
        "risk": "review" if findings or not is_test or not has_ci else "no_pattern_detected",
        "notice": "기초 정적 패턴 검사만 수행했습니다. 취약점 부재 또는 출시 안전성을 보증하지 않습니다.",
        "not_run": ["runtime", "unit_tests", "e2e", "dependency_audit",
                    "dynamic_security", "load", "resource_profile", "soak"],
    }
