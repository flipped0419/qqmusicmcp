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

@pytest.mark.asyncio
async def test_my_likes_not_mutated():
    with pytest.raises(ValueError):
        await WriteGate().preview("remove_song", directory_id=201, song_id=1)
    with pytest.raises(ValueError):
        await WriteGate().apply("nonexistent")

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

def test_private_cookie_store_and_status(tmp_path, monkeypatch):
    from qqmusicmcp.secrets_config import session_cookie, api_key
    from qqmusicmcp.library import uin_from_cookie, read_cookie
    import json
    path = tmp_path / 'private' / 'credentials.json'
    path.parent.mkdir(mode=0o700)
    path.write_text(json.dumps({
        "qqmusic_api_key": "qmk-fake-test-only",
        "qqmusic_cookie": "uin=o12345678; p_skey=fake-for-test-only"
    }))
    path.chmod(0o600)
    monkeypatch.setenv('QQMUSIC_SECRETS_FILE', str(path))
    monkeypatch.delenv('QQMUSIC_COOKIE', raising=False)
    monkeypatch.delenv('QQMUSIC_API_KEY', raising=False)
    assert api_key() == "qmk-fake-test-only"
    assert read_cookie() == session_cookie()
    assert uin_from_cookie(read_cookie()) == "12345678"


@pytest.mark.asyncio
async def test_personal_playlist_and_likes_mock(monkeypatch):
    from qqmusicmcp import library
    monkeypatch.setattr(library, 'read_cookie', lambda: 'uin=o7654321; p_skey=sample')
    async def mock_get(url, params):
        if 'fcg_user_created_diss' in url:
            return {"data": {"disslist": [
                {"dirid": 201, "tid": 88101, "diss_name": "我喜欢", "song_cnt": 1},
                {"dirid": 321, "tid": 88102, "diss_name": "测试歌单", "song_cnt": 0}
            ]}}
        return {"cdlist": [{"songlist": [
            {"id": 42, "mid": "ABC123", "name": "Testing", "singer": [{"name": "Test"}]}
        ]}]}
    monkeypatch.setattr(library, 'get_json', mock_get)
    all_lists = await library.personal_playlists()
    assert len(all_lists) == 2
    assert all_lists[0]['directory_id'] == 201
    export = await library.liked_songs()
    assert len(export['songs']) == 1
    assert export['songs'][0]['mid'] == "ABC123"


@pytest.mark.asyncio
async def test_reject_truncated_liked_export(monkeypatch):
    from qqmusicmcp import library
    async def get_json(url, params):
        if 'fcg_user_created_diss' in url:
            return {"data": {"disslist": [{"dirid": 201, "tid": 1, "song_cnt": 5}]}}
        return {"cdlist": [{"songlist": [{"mid": "TEST", "id": 1, "name": "Test"}]}]}
    monkeypatch.setattr(library, 'read_cookie', lambda: 'uin=o321')
    monkeypatch.setattr(library, 'get_json', get_json)
    with pytest.raises(library.LibraryError, match='truncated'):
        await library.liked_songs()



@pytest.mark.asyncio
async def test_resolve_song_mid_with_mock_http(monkeypatch):
    from qqmusicmcp import library
    monkeypatch.setattr(library, 'read_cookie', lambda: 'uin=o98765; p_skey=sample')
    def handler(req):
        assert req.url.host == 'u.y.qq.com'
        assert req.method == 'POST'
        request_body = json.loads(req.content)
        assert request_body['req_0']['param']['song_mid'] == 'AB123'
        return httpx.Response(200, json={'req_0': {
            'code': 0, 'data': {'track_info': {
                'id': 12345, 'type': 0, 'name': 'Mock', 'singer': [{'name': 'Artist'}]}}
        }})
    result=await library.song_write_identity('AB123', transport=httpx.MockTransport(handler))
    assert result=={'mid':'AB123','song_id':12345,'song_type':0,
                    'name':'Mock','singers':['Artist']}
    with pytest.raises(ValueError):
        await library.song_write_identity('../../invalid')


def test_default_credentials_sibling_of_checkout():
    from pathlib import Path
    from qqmusicmcp.secrets_config import DEFAULT_SECRETS_FILE
    project_dir = Path(__file__).resolve().parents[1]
    assert DEFAULT_SECRETS_FILE == project_dir.parent / '.qqmusicmcp' / 'credentials.json'
    assert project_dir not in DEFAULT_SECRETS_FILE.parents
