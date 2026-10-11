import json
import pytest
import httpx
from qqmusicmcp.official import OfficialClient
from qqmusicmcp.writes import WriteGate
from qqmusicmcp.server import mcp

@pytest.mark.asyncio
async def test_official_wire_protocol():
    def handler(req):
        assert req.url.path == "/discover/search"
        assert req.headers["Authorization"] == "Bearer example-only"
        assert json.loads(req.content) == {"params":{"keyword":"test"},"comm":{"skill_version":"0.0.3"}}
        return httpx.Response(200,json={"songs":[]})
    c=OfficialClient(key="example-only",transport=httpx.MockTransport(handler))
    try:
        assert await c.request("/discover/search", {"keyword":"test"}) == {"songs":[]}
    finally: await c.close()

@pytest.mark.asyncio
async def test_no_arbitrary_endpoint():
    c=OfficialClient(key="sample")
    try:
        with pytest.raises(ValueError): await c.request("/unexpected")
    finally: await c.close()

def test_my_likes_not_mutated():
    with pytest.raises(ValueError): WriteGate().preview("remove_song",directory_id=201,song_id=1)
    with pytest.raises(PermissionError): WriteGate().apply("nonexistent")

@pytest.mark.asyncio
async def test_mcp_registered_tools():
    names={t.name for t in await mcp.list_tools()}
    assert {"qqmusic_search","qqmusic_liked_songs","qqmusic_preview_write","qqmusic_apply_write"} <= names
