"""Privacy-safe connectivity check: prints counts/status only, never personal tracks.

Cookie must already be configured via scripts/configure_cookie.py.
"""
from __future__ import annotations
import asyncio
from qqmusicmcp.library import LibraryError, personal_playlists, liked_songs
from qqmusicmcp.secrets_config import session_cookie

async def main():
    if not session_cookie():
        print('Cookie 未配置；请先运行 configure_cookie.py')
        return
    try:
        lists = await personal_playlists()
        print('个人歌单读取: 成功')
        print('歌单数量:', len(lists))
        print('包含「我喜欢」:', any(p['directory_id'] == 201 for p in lists))
    except Exception as exc:
        print('个人歌单读取: 失败', type(exc).__name__)
        return
    await asyncio.sleep(1)
    try:
        liked = await liked_songs()
        print('「我喜欢」读取: 成功')
        print('歌曲数量:', len(liked['songs']))
    except Exception as exc:
        print('「我喜欢」读取: 失败', type(exc).__name__)

if __name__ == '__main__':
    asyncio.run(main())
