"""Third-party QQ Music account write requests, adapted from baoozak/qqmusic-mcp (MIT).

These undocumented endpoints may break at any moment. All callers must enforce
an explicit, time-limited probe and preview before invoking methods in this file.
"""
from __future__ import annotations
import httpx
from .library import read_cookie, uin_from_cookie

class WriteAPIError(RuntimeError):
    pass

def csrf_token(cookie: str) -> int:
    parts = dict(part.strip().split('=', 1) for part in cookie.split(';') if '=' in part)
    skey = parts.get('p_skey') or parts.get('skey') or ''
    token = 5381
    for char in skey:
        token += (token << 5) + ord(char)
    return token & 0x7fffffff

class WriteBackend:
    async def request(self, module: str, method: str, params: dict):
        if (module, method) not in {
            ('music.musicasset.PlaylistBaseWrite', 'AddPlaylist'),
            ('music.musicasset.PlaylistBaseWrite', 'DelPlaylist'),
            ('music.musicasset.PlaylistDetailWrite', 'AddSonglist'),
            ('music.musicasset.PlaylistDetailWrite', 'DelSonglist'),
        }:
            raise ValueError('unsupported QQ Music write endpoint')
        cookie = read_cookie()
        user = uin_from_cookie(cookie)
        try:
            async with httpx.AsyncClient(timeout=25, headers={
                'Cookie': cookie, 'Referer': 'https://y.qq.com/',
                'Origin': 'https://y.qq.com', 'User-Agent': 'Mozilla/5.0',
            }) as client:
                response = await client.post(
                    'https://u.y.qq.com/cgi-bin/musicu.fcg',
                    params={'format': 'json', 'g_tk': csrf_token(cookie)},
                    json={'comm': {'ct': 24, 'cv': 0, 'uin': user},
                          'req_0': {'module': module, 'method': method, 'param': params}},
                )
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError):
            raise WriteAPIError('QQ Music rejected write request or returned invalid JSON') from None
        if not isinstance(result, dict):
            raise WriteAPIError('unexpected QQ Music write response')
        detail = result.get('req_0')
        if not isinstance(detail, dict):
            raise WriteAPIError('QQ Music write response has no req_0')
        if detail.get('code') != 0:
            raise WriteAPIError('QQ Music write failed; service returned a nonzero result code')
        return detail.get('data') or {}

    async def create_playlist(self, name: str) -> int:
        if not name.strip() or len(name) > 80:
            raise ValueError('name required, max 80 characters')
        data = await self.request('music.musicasset.PlaylistBaseWrite', 'AddPlaylist',
                                  {'dirName': name, 'dirDesc': '', 'dirPicUrl': '', 'taglist': []})
        result = data.get('result') if isinstance(data, dict) else None
        directory_id = result.get('dirId') if isinstance(result, dict) else result
        if not str(directory_id).isdigit() or int(directory_id) <= 0:
            raise WriteAPIError('QQ Music returned no valid new directory ID')
        return int(directory_id)

    async def edit_song(self, action: str, directory_id: int, song_id: int, song_type: int = 0):
        if directory_id <= 0 or directory_id == 201:
            raise ValueError('cannot modify My Likes or an invalid playlist')
        if song_id <= 0 or song_type < 0:
            raise ValueError('invalid numeric song ID or song type')
        if action not in {'add', 'remove'}:
            raise ValueError('unsupported song edit')
        method = 'AddSonglist' if action == 'add' else 'DelSonglist'
        await self.request('music.musicasset.PlaylistDetailWrite', method,
                           {'dirId': directory_id,
                            'v_songInfo': [{'songType': song_type, 'songId': song_id}]})

    async def delete_playlist(self, directory_id: int):
        if directory_id <= 0 or directory_id == 201:
            raise ValueError('cannot delete My Likes or an invalid playlist')
        await self.request('music.musicasset.PlaylistBaseWrite', 'DelPlaylist',
                           {'dirId': directory_id})
