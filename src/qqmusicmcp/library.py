"""Optional unofficial QQ Music personal library read API.

Code inspired by baoozak/qqmusic-mcp's MIT-licensed client. No Windows DPAPI.
Personal session credential never leaves the server except to QQ Music itself.
"""
from __future__ import annotations
import os
import re
import httpx

class LibraryError(RuntimeError): pass

def read_cookie():
    raw = os.getenv("QQMUSIC_COOKIE", "")
    if not raw:
        raise LibraryError("QQMUSIC_COOKIE is not configured")
    if "\n" in raw or "\r" in raw:
        raise LibraryError("invalid cookie")
    return raw

def uin_from_cookie(raw: str):
    def field(k):
        m = re.search(r"(?:^|;\s*)" + re.escape(k) + r"=([^;]*)", raw)
        return m.group(1) if m else ""
    value = (field("wxuin") if field("login_type") == "2" else field("uin")) or field("uin") or field("p_uin")
    number = value.lstrip("o")
    if not number.isdigit():
        raise LibraryError("QQ Music cookie has no usable account ID")
    return number

async def get_json(url, params):
    cookie = read_cookie()
    try:
        async with httpx.AsyncClient(timeout=25, headers={"Cookie": cookie,
            "Referer": "https://y.qq.com/", "User-Agent": "Mozilla/5.0"}) as client:
            res = await client.get(url, params=params)
            res.raise_for_status()
            return res.json()
    except (httpx.HTTPError, ValueError):
        raise LibraryError("QQ Music personal API request failed or returned an unexpected format") from None

async def personal_playlists():
    uin = uin_from_cookie(read_cookie())
    data = await get_json("https://c.y.qq.com/rsc/fcgi-bin/fcg_user_created_diss",
        {"hostuin": uin, "sin": 0, "size": 200, "loginUin": uin, "format": "json", "platform": "yqq.json"})
    playlists = data.get("data", {}).get("disslist")
    if not isinstance(playlists, list):
        raise LibraryError("QQ Music playlist interface changed or login expired")
    return [{"directory_id": p.get("dirid"), "playlist_id": p.get("tid") or p.get("dissid"),
             "name": p.get("diss_name") or p.get("dissname"),
             "song_count": p.get("song_cnt") or p.get("songnum")} for p in playlists]

async def playlist_tracks(playlist_id: int):
    uin = uin_from_cookie(read_cookie())
    data = await get_json("https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg",
        {"type": 1, "utf8": 1, "onlysong": 0, "disstid": playlist_id,
         "loginUin": uin, "format": "json"})
    cdlist = data.get("cdlist", [])
    if not cdlist or not isinstance(cdlist[0].get("songlist"), list):
        raise LibraryError("QQ Music song list interface changed or login expired")
    return [{"mid": p.get("mid") or p.get("songmid"),
             "song_id": p.get("id") or p.get("songid"),
             "name": p.get("name") or p.get("songname"),
             "type": p.get("type") or p.get("songtype", 0),
             "singers": [s.get("name") for s in p.get("singer", []) if isinstance(s, dict)]}
            for p in cdlist[0]["songlist"]]

async def liked_songs():
    lists = await personal_playlists()
    liked = next((p for p in lists if p["directory_id"] == 201), None)
    if not liked or not liked["playlist_id"]:
        raise LibraryError("My Likes not found")
    songs = await playlist_tracks(int(liked["playlist_id"]))
    if liked["song_count"] and len(songs) < int(liked["song_count"]):
        raise LibraryError("My Likes appears truncated; refusing incomplete export")
    return {"playlist": liked, "songs": songs}
