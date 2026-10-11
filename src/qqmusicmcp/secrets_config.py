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

def _private_credentials() -> dict[str, str]:
    path = credentials_path()
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {}
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise CredentialsError('QQ Music credentials file must be regular and private (0600)')
    if path.parent.stat().st_mode & 0o077:
        raise CredentialsError('QQ Music credentials directory must be private (0700)')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise CredentialsError('QQ Music credentials file cannot be read') from None
    if not isinstance(data, dict) or any(
        not isinstance(data.get(name, ''), str)
        for name in ('qqmusic_api_key', 'qqmusic_cookie')
    ):
        raise CredentialsError('QQ Music credentials file is not valid')
    return data


def api_key() -> str:
    return os.getenv('QQMUSIC_API_KEY') or _private_credentials().get('qqmusic_api_key', '')


def session_cookie() -> str:
    return os.getenv('QQMUSIC_COOKIE') or _private_credentials().get('qqmusic_cookie', '')
