"""Normalize repository inputs without allowing arbitrary network destinations."""
import re
from urllib.parse import urlsplit


def parse_repository(value: str):
    value = value.strip()
    error = 'GitHub 저장소 주소를 입력하세요. 예: https://github.com/owner/repository 또는 owner/repository'
    if not value or any(c.isspace() or ord(c) < 32 for c in value) or '\\' in value:
        raise ValueError(error)
    if value.startswith('git@github.com:'):
        value = 'https://github.com/' + value[len('git@github.com:'):]
    elif re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+/?', value) and not value.lower().startswith(('github.com/', 'www.github.com/')):
        value = 'https://github.com/' + value
    elif value.lower().startswith(('github.com/', 'www.github.com/')):
        value = 'https://' + value
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'http', 'https'} or parsed.hostname not in {'github.com', 'www.github.com'}
                or parsed.username or parsed.password or parsed.port is not None):
            raise ValueError(error)
    except ValueError:
        raise ValueError(error) from None
    parts = parsed.path.strip('/').split('/')
    if len(parts) < 2:
        raise ValueError(error)
    owner, repo = parts[:2]
    if repo.endswith('.git'):
        repo = repo[:-4]
    if (not re.fullmatch(r'[A-Za-z0-9-]{1,39}', owner)
            or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', repo) or repo in {'.', '..'}):
        raise ValueError(error)
    if len(parts) > 2 and (parts[2] not in {'tree', 'blob', 'pull', 'pulls', 'issues', 'actions', 'releases', 'commit', 'commits'}
                           or any(p in {'', '.', '..'} for p in parts[2:])):
        raise ValueError(error)
    return owner, repo
