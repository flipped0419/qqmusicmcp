"""Credential store for QwenPaw; never logs secret contents.

Environment variables take precedence. On QwenPaw the private JSON file is
persisted alongside (not inside) the Git checkout on its NAS mount.
"""
from __future__ import annotations
import json
import os
import stat
from pathlib import Path

DEFAULT_SECRETS_FILE = Path('/app/working/shellmcp-workspace/.qqmusicmcp/credentials.json')

class CredentialsError(RuntimeError):
    pass

def credentials_path() -> Path:
    override = os.getenv('QQMUSIC_SECRETS_FILE', '').strip()
    return Path(override).expanduser() if override else DEFAULT_SECRETS_FILE

def api_key() -> str:
    env_value = os.getenv('QQMUSIC_API_KEY', '')
    if env_value:
        return env_value
    path = credentials_path()
    try:
        info = path.lstat()
    except FileNotFoundError:
        return ''
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise CredentialsError('QQ Music credentials file must be regular and private (0600)')
    if path.parent.stat().st_mode & 0o077:
        raise CredentialsError('QQ Music credentials directory must be private (0700)')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise CredentialsError('QQ Music credentials file cannot be read') from None
    if not isinstance(data, dict) or not isinstance(data.get('qqmusic_api_key', ''), str):
        raise CredentialsError('QQ Music credentials file is not valid')
    return data.get('qqmusic_api_key', '')
