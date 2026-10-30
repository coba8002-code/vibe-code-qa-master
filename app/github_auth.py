"""Use existing local GitHub credentials without prompts, storage or logging."""
import os
import shutil
import subprocess


def github_token():
    configured = os.getenv('QA_GITHUB_TOKEN', '').strip()
    if configured:
        return configured
    git = shutil.which('git')
    if not git:
        return ''
    try:
        result = subprocess.run(
            [git, 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
            capture_output=True, text=True, timeout=10,
            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'},
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            return ''
        fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        return fields.get('password', '')
    except (OSError, subprocess.TimeoutExpired):
        return ''


def github_error(status):
    if status == 404:
        return '저장소를 찾거나 읽을 수 없습니다. 비공개 저장소는 이 PC의 GitHub 로그인 또는 QA_GITHUB_TOKEN에 해당 저장소 읽기 권한이 필요합니다.'
    if status == 401:
        return 'GitHub 인증이 만료되었거나 유효하지 않습니다. 이 PC의 GitHub 로그인을 갱신하세요.'
    if status in (403, 429):
        return 'GitHub 접근 권한 또는 API 호출 제한으로 검수가 중단됐습니다. 저장소 권한과 호출 한도를 확인하세요.'
    return f'GitHub 응답 오류({status})로 저장소를 가져오지 못했습니다.'
