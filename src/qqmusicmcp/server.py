"""Single stdio MCP server with official + optional personal library tools."""
from __future__ import annotations
import os
from mcp.server.fastmcp import FastMCP
from .official import OfficialClient
from .library import personal_playlists, playlist_tracks, liked_songs
from .writes import WriteGate, writes_enabled

mcp = FastMCP("QQ Music Unified MCP")
gate = WriteGate()

async def call(path, params=None):
    client = OfficialClient()
    try:
        return await client.request(path, params)
    finally:
        await client.close()

@mcp.tool()
async def qqmusic_status():
    """Show provider availability without revealing authentication secrets."""
    return {"official_api_configured": bool(os.getenv("QQMUSIC_API_KEY")),
            "personal_library_configured": bool(os.getenv("QQMUSIC_COOKIE")),
            "writes_enabled_in_config": writes_enabled(),
            "writes_operational": False, "official_skill_version": "0.0.3"}

@mcp.tool()
async def qqmusic_search(keyword: str, type: str = "0", page: int = 0):
    """Search QQ Music songs (0), albums (1), playlists (2), MV (3), radio (4), singers (5)."""
    if not keyword.strip() or len(keyword) > 100 or type not in {"0","1","2","3","4","5"} or not 0 <= page <= 100:
        raise ValueError("invalid search parameters")
    return await call("/discover/search", {"keyword": keyword, "type": type, "page": page})

@mcp.tool()
async def qqmusic_daily_mix():
    """Official daily recommended songs."""
    return await call("/discover/daily-mix")

@mcp.tool()
async def qqmusic_radio():
    """Official Guess You Like recommendations."""
    return await call("/discover/radio")

@mcp.tool()
async def qqmusic_ai_playlists():
    """Official AI playlist recommendations."""
    return await call("/discover/ai-playlists", {"reqType": "all"})

@mcp.tool()
async def qqmusic_charts():
    """Official chart group list."""
    return await call("/charts")

@mcp.tool()
async def qqmusic_chart_detail(top_id: int, page: int = 0):
    """Official chart tracks."""
    if top_id <= 0 or not 0 <= page <= 100: raise ValueError("invalid chart params")
    return await call("/charts/detail", {"topId": top_id, "page": page})

@mcp.tool()
async def qqmusic_playlist_detail(diss_id: int, page: int = 0):
    """Official public playlist tracks using dissId."""
    if diss_id <= 0 or not 0 <= page <= 100: raise ValueError("invalid playlist params")
    return await call("/playlists/detail", {"dissId": diss_id, "page": page})

@mcp.tool()
async def qqmusic_listening_report(period: str = "m", start_time: int = 0):
    """Official listening report: d=day, w=week, m=month."""
    if period not in {"d","w","m"} or start_time < 0: raise ValueError("invalid report params")
    params = {"timeKey": period}
    if period != "m" and start_time: params["startTime"] = start_time
    return await call("/me/report", params)

@mcp.tool()
async def qqmusic_personal_playlists():
    """List personal playlists using a private session cookie."""
    return await personal_playlists()

@mcp.tool()
async def qqmusic_personal_playlist_tracks(playlist_id: int):
    """Read playlist song records using public playlist ID (not directory_id)."""
    if playlist_id <= 0: raise ValueError("playlist_id must be positive")
    return await playlist_tracks(playlist_id)

@mcp.tool()
async def qqmusic_liked_songs():
    """Read My Likes without changing hearts."""
    return await liked_songs()

@mcp.tool()
async def qqmusic_preview_write(operation: str, name: str = "", directory_id: int = 0, song_id: int = 0):
    """Preview a proposed change (create playlist, add/remove song, delete playlist). Never writes."""
    return gate.preview(operation, name, directory_id, song_id)

@mcp.tool()
async def qqmusic_probe_write():
    """Write probe placeholder. Does NOT mutate even with writes configured."""
    return {"status": "not_implemented", "message": "Temporary playlist lifecycle must be tested before enabling writes"}

@mcp.tool()
async def qqmusic_apply_write(confirmation_token: str):
    """Write application is disabled in v0.1.0 even with explicit confirmation."""
    gate.apply(confirmation_token)

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
