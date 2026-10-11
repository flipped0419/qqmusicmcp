"""Optional unofficial QQ Music personal library read API.

Code inspired by baoozak/qqmusic-mcp's MIT-licensed client. No Windows DPAPI.
Personal session credential never leaves the server except to QQ Music itself.
"""

from __future__ import annotations
import re
import httpx
from .secrets_config import session_cookie


class LibraryError(RuntimeError):
    pass


def read_cookie():
    raw = session_cookie()
    if not raw:
        raise LibraryError("QQMUSIC_COOKIE is not configured")
    if "\n" in raw or "\r" in raw:
        raise LibraryError("invalid cookie")
    return raw


def uin_from_cookie(raw: str):
    def field(k):
        m = re.search(r"(?:^|;\s*)" + re.escape(k) + r"=([^;]*)", raw)
        return m.group(1) if m else ""

    value = (
        (field("wxuin") if field("login_type") == "2" else field("uin"))
        or field("uin")
        or field("p_uin")
    )
    number = value.lstrip("o")
    if not number.isdigit():
        raise LibraryError("QQ Music cookie has no usable account ID")
    return number


async def get_json(url, params):
    cookie = read_cookie()
    try:
        async with httpx.AsyncClient(
            timeout=25,
            headers={
                "Cookie": cookie,
                "Referer": "https://y.qq.com/",
                "User-Agent": "Mozilla/5.0",
            },
        ) as client:
            res = await client.get(url, params=params)
            res.raise_for_status()
            return res.json()
    except (httpx.HTTPError, ValueError):
        raise LibraryError(
            "QQ Music personal API request failed or returned an unexpected format"
        ) from None


async def personal_playlists():
    uin = uin_from_cookie(read_cookie())
    data = await get_json(
        "https://c.y.qq.com/rsc/fcgi-bin/fcg_user_created_diss",
        {
            "hostuin": uin,
            "sin": 0,
            "size": 200,
            "loginUin": uin,
            "format": "json",
            "platform": "yqq.json",
        },
    )
    playlists = data.get("data", {}).get("disslist")
    if not isinstance(playlists, list):
        raise LibraryError("QQ Music playlist interface changed or login expired")
    return [
        {
            "directory_id": p.get("dirid"),
            "playlist_id": p.get("tid") or p.get("dissid"),
            "name": p.get("diss_name") or p.get("dissname"),
            "song_count": p.get("song_cnt") or p.get("songnum"),
        }
        for p in playlists
    ]


async def playlist_tracks(playlist_id: int):
    uin = uin_from_cookie(read_cookie())
    data = await get_json(
        "https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg",
        {
            "type": 1,
            "utf8": 1,
            "onlysong": 0,
            "disstid": playlist_id,
            "loginUin": uin,
            "format": "json",
        },
    )
    cdlist = data.get("cdlist", [])
    if not cdlist or not isinstance(cdlist[0].get("songlist"), list):
        raise LibraryError("QQ Music song list interface changed or login expired")
    return [
        {
            "mid": p.get("mid") or p.get("songmid"),
            "song_id": p.get("id") or p.get("songid"),
            "name": p.get("name") or p.get("songname"),
            "type": p.get("type") or p.get("songtype", 0),
            "singers": [
                s.get("name") for s in p.get("singer", []) if isinstance(s, dict)
            ],
        }
        for p in cdlist[0]["songlist"]
    ]


async def liked_songs():
    lists = await personal_playlists()
    liked = next((p for p in lists if p["directory_id"] == 201), None)
    if not liked or not liked["playlist_id"]:
        raise LibraryError("My Likes not found")
    songs = await playlist_tracks(int(liked["playlist_id"]))
    if liked["song_count"] and len(songs) < int(liked["song_count"]):
        raise LibraryError("My Likes appears truncated; refusing incomplete export")
    return {"playlist": liked, "songs": songs}


async def song_write_identity(
    song_mid: str, transport: httpx.AsyncBaseTransport | None = None
) -> dict:
    """Resolve an official-search MID into the numerical ID needed for safe playlist additions.

    QQ Music's old website search endpoint can return HTTP 500. A targeted
    musicu song-detail lookup avoids depending on the broken catalog endpoint.
    """
    if not re.fullmatch(r"[0-9A-Za-z]{1,128}", song_mid):
        raise ValueError("invalid song MID")
    cookie = read_cookie()
    uin = uin_from_cookie(cookie)
    try:
        async with httpx.AsyncClient(
            timeout=25,
            transport=transport,
            headers={
                "Cookie": cookie,
                "Referer": "https://y.qq.com/",
                "User-Agent": "Mozilla/5.0",
            },
        ) as client:
            response = await client.post(
                "https://u.y.qq.com/cgi-bin/musicu.fcg",
                params={"format": "json"},
                json={
                    "comm": {"ct": 24, "cv": 0, "uin": uin},
                    "req_0": {
                        "module": "music.pf_song_detail_svr",
                        "method": "get_song_detail_yqq",
                        "param": {"song_mid": song_mid},
                    },
                },
            )
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError):
        raise LibraryError("QQ Music song detail lookup failed") from None
    req = body.get("req_0") if isinstance(body, dict) else None
    if not isinstance(req, dict) or req.get("code") != 0:
        raise LibraryError("QQ Music song detail API declined the request")
    data = req.get("data")
    track = data.get("track_info") if isinstance(data, dict) else None
    if not isinstance(track, dict):
        raise LibraryError("QQ Music song detail response has changed")
    try:
        sid = int(track.get("id", 0))
        song_type = int(track.get("type", 0))
    except (TypeError, ValueError):
        raise LibraryError("QQ Music detail has no numeric song identity") from None
    if sid <= 0 or song_type < 0:
        raise LibraryError("QQ Music detail has an invalid numeric song identity")
    singers = track.get("singer")
    return {
        "mid": song_mid,
        "song_id": sid,
        "song_type": song_type,
        "name": str(track.get("name") or ""),
        "singers": [str(s.get("name") or "") for s in singers if isinstance(s, dict)]
        if isinstance(singers, list)
        else [],
    }
