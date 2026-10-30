"""Read-only GitHub snapshot acquisition, pinned to a source commit."""
import json
import re
import urllib.error
import urllib.request
import zipfile
import tempfile
from pathlib import PurePosixPath
from app.github_auth import github_token, github_error

from app.scanner import MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES, scan, EXTENSIONS, NAMES, EXCLUDE

SHA_PATTERN = re.compile(r"^[a-fA-F0-9]{40}$")
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


class SnapshotError(Exception):
    pass


def _request(url):
    headers = {"User-Agent": "vibe-qa-master", "Accept": "application/vnd.github+json"}
    token = github_token()
    request = urllib.request.Request(url, headers=headers)
    if token:
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    return request


def fetch_snapshot(owner, repo):
    with tempfile.TemporaryFile() as archive_file:
        return _fetch_snapshot(owner, repo, archive_file)


def _fetch_snapshot(owner, repo, archive_file):
    """Read-only GitHub access; bounded temporary ZIP, never extracted."""
    try:
        with urllib.request.urlopen(_request(f"https://api.github.com/repos/{owner}/{repo}"), timeout=15) as response:
            info = json.load(response)
        branch = info.get("default_branch", "")
        if not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", branch) or ".." in branch:
            raise SnapshotError("Invalid default branch")
        with urllib.request.urlopen(_request(f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"), timeout=15) as response:
            commit = json.load(response)
        sha = commit.get("sha", "")
        if not SHA_PATTERN.fullmatch(sha):
            raise SnapshotError("Invalid GitHub revision")
        with urllib.request.urlopen(_request(f"https://api.github.com/repos/{owner}/{repo}/zipball/{sha}"), timeout=30) as response:
            downloaded = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > MAX_ARCHIVE_BYTES:
                    raise SnapshotError("저장소 ZIP이 다운로드 한도 256MB를 초과합니다. 로컬 폴더 검수를 사용하세요.")
                archive_file.write(chunk)
            archive_file.seek(0)
    except urllib.error.HTTPError as exc:
        raise SnapshotError(github_error(exc.code)) from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise SnapshotError("GitHub read unavailable: check repository access") from exc

    try:
        with zipfile.ZipFile(archive_file) as archive:
            items = []
            total = 0
            skipped = 0
            for file in archive.infolist():
                if file.is_dir():
                    continue
                name = "/".join(file.filename.split("/")[1:])
                if not name:
                    continue
                path = PurePosixPath(name)
                if (any(part in EXCLUDE for part in path.parts)
                        or (path.suffix.lower() not in EXTENSIONS and path.name not in NAMES)):
                    skipped += 1
                    continue
                if len(items) >= MAX_FILES or file.file_size > MAX_FILE_BYTES:
                    skipped += 1
                    continue
                if total + file.file_size > MAX_TOTAL_BYTES:
                    skipped += 1
                    continue
                total += file.file_size
                items.append((name, archive.read(file)))
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise SnapshotError("Unable to read repository snapshot") from exc

    result = scan(items, f"github:{owner}/{repo}@{sha}")
    result["files_skipped"] += skipped
    return {"branch": branch, "revision": sha, "visibility": info.get("visibility", "unknown"),
            "report": result}
