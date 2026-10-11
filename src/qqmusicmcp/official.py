"""Tencent Music official qqmusic-skills v0.0.3 API implementation."""
from __future__ import annotations
import os
from typing import Any
import httpx

SKILL_VERSION = "0.0.3"
ENDPOINTS = {"/discover/search", "/discover/daily-mix", "/discover/radio",
             "/discover/ai-playlists", "/charts", "/charts/detail",
             "/playlists/detail", "/me/report"}

class OfficialError(RuntimeError): pass

class OfficialClient:
    def __init__(self, key: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.key = key if key is not None else os.getenv("QQMUSIC_API_KEY", "")
        self.http = httpx.AsyncClient(base_url="https://a.y.qq.com", timeout=25, transport=transport)

    async def close(self):
        await self.http.aclose()

    async def request(self, path: str, params: dict[str, Any] | None = None):
        if path not in ENDPOINTS:
            raise ValueError("unsupported official API endpoint")
        if not self.key:
            raise OfficialError("QQMUSIC_API_KEY is not configured on the server")
        try:
            resp = await self.http.post(path,
                json={"params": params or {}, "comm": {"skill_version": SKILL_VERSION}},
                headers={"Authorization": f"Bearer {self.key}"})
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            raise OfficialError("QQ Music official API request failed") from None
        if not isinstance(data, dict):
            raise OfficialError("invalid QQ Music response")
        if data.get("ret") not in (None, 0) or data.get("sub_ret") not in (None, 0):
            raise OfficialError("QQ Music official API returned an error")
        return data
