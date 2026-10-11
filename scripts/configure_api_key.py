"""Interactive credential setup; does not echo the key."""
from __future__ import annotations
import getpass
import json
import os
import sys
import tempfile
from qqmusicmcp.secrets_config import credentials_path

def main() -> int:
    if not sys.stdin.isatty():
        print('需要交互式终端（TTY）。请不要把 API Key 作为命令参数或发到聊天中。', file=sys.stderr)
        return 2
    key = getpass.getpass('粘贴 QQ 音乐官方 API Key（输入不回显）：').strip()
    if not key.startswith('qmk-') or len(key) <= 6 or any(ch.isspace() for ch in key):
        print('Key 格式不正确，未保存。', file=sys.stderr)
        return 2
    path = credentials_path()
    if path.is_symlink():
        print('拒绝写入符号链接目标。', file=sys.stderr)
        return 2
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    previous = {}
    if path.exists():
        from qqmusicmcp.secrets_config import api_key
        api_key()
        previous = json.loads(path.read_text(encoding='utf-8'))
    previous['qqmusic_api_key'] = key
    fd, name = tempfile.mkstemp(prefix='.qqmusic-credentials-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(previous, output, ensure_ascii=False)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    print('QQ 音乐 API Key 已保存到服务器的私有目录（0600），不会显示密钥内容。')
    return 0

if __name__ == '__main__':
    sys.exit(main())
