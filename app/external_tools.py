"""Find installed vendor tools even when Explorer has an older PATH."""
import os
from pathlib import Path
import shutil


def find_tool(name):
    located = shutil.which(name)
    if located:
        return located
    if os.name != 'nt':
        return None
    return windows_tool(name, os.environ)


def windows_tool(name, environment):
    local = environment.get('LOCALAPPDATA')
    program_files = environment.get('ProgramFiles')
    candidates = []
    if name == 'docker':
        if local:
            candidates.append(Path(local) / 'Programs/DockerDesktop/resources/bin/docker.exe')
        if program_files:
            candidates.append(Path(program_files) / 'Docker/Docker/resources/bin/docker.exe')
    elif name == 'codex' and local:
        candidates.extend((Path(local) / 'OpenAI/Codex/bin').glob('*/codex.exe'))
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return next((str(p) for p in candidates if p.is_file()), None)
