"""Store the optional QQ Music browser Cookie without echo or shell history.

Run interactively on the QwenPaw server. Cookie is never printed back.
"""
from __future__ import annotations
import getpass
import json
import os
import re
import sys
import tempfile
from qqmusicmcp.secrets_config import credentials_path, api_key, session_cookie

COOKIE_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


def validate_cookie(raw: str) -> bool:
    if not raw or len(raw) > 16384 or '\n' in raw or '\r' in raw:
        return False
    if raw.lower().startswith('cookie:'):
        return False
    names = []
    for part in raw.split(';'):
        name, separator, value = part.strip().partition('=')
        if not separator or not COOKIE_NAME.fullmatch(name):
            return False
        names.append(name)
    return any(name in names for name in ('uin', 'p_uin', 'wxuin'))


def main() -> int:
    if not sys.stdin.isatty():
        print('需要在交互式终端中运行。请勿把 Cookie 放进命令参数或聊天。', file=sys.stderr)
        return 2
    raw = getpass.getpass('粘贴 y.qq.com 的 Cookie 值（不会回显）：').strip()
    if not validate_cookie(raw):
        print('Cookie 格式不符合要求（应为 name=value; name2=value2，包含 uin 等字段），未保存。', file=sys.stderr)
        return 2
    path = credentials_path()
    if path.is_symlink():
        print('拒绝向符号链接写入凭据。', file=sys.stderr)
        return 2
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    previous = {}
    if path.exists():
        # Validate existing file permissions without printing its content.
        api_key()
        session_cookie()
        previous = json.loads(path.read_text(encoding='utf-8'))
    previous['qqmusic_cookie'] = raw
    fd, tmp = tempfile.mkstemp(prefix='.qqmusic-credentials-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(previous, stream, ensure_ascii=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print('QQ 音乐 Cookie 已保存在私有目录中。请勿把 Cookie 发送到聊天或 GitHub。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
