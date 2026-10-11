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

def test_private_file_config(tmp_path, monkeypatch):
    from qqmusicmcp.secrets_config import api_key, CredentialsError
    path = tmp_path / 'private' / 'credentials.json'
    path.parent.mkdir(mode=0o700)
    path.write_text('{"qqmusic_api_key":"qmk-example-fake"}')
    path.chmod(0o600)
    monkeypatch.setenv('QQMUSIC_SECRETS_FILE', str(path))
    monkeypatch.delenv('QQMUSIC_API_KEY', raising=False)
    assert api_key() == 'qmk-example-fake'
    path.chmod(0o644)
    with pytest.raises(CredentialsError):
        api_key()


def test_secrets_not_saved_with_noninteractive_stdin():
    from qqmusicmcp.secrets_config import DEFAULT_SECRETS_FILE
    assert str(DEFAULT_SECRETS_FILE).endswith('/.qqmusicmcp/credentials.json')
