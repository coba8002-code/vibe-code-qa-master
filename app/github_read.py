"""Read-only GitHub snapshot acquisition, pinned to a source commit."""
import io
import json
import os
import re
import urllib.error
import urllib.request
import zipfile

from app.scanner import MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES, scan

SHA_PATTERN = re.compile(r"^[a-fA-F0-9]{40}$")


class SnapshotError(Exception):
    pass


def _request(url):
    headers = {"User-Agent": "vibe-qa-master", "Accept": "application/vnd.github+json"}
    token = os.getenv("QA_GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def fetch_snapshot(owner, repo):
    """No writes, shell commands, checkout, or untrusted archive extraction."""
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
            payload = response.read(MAX_TOTAL_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise SnapshotError("GitHub read unavailable: check repository access") from exc
    if len(payload) > MAX_TOTAL_BYTES:
        raise SnapshotError("Repository archive exceeds first-pass limit")

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            items = []
            total = 0
            skipped = 0
            for file in archive.infolist():
                if file.is_dir():
                    continue
                name = "/".join(file.filename.split("/")[1:])
                if not name:
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
