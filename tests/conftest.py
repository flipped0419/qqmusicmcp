import pytest
from qqmusicmcp import writes


@pytest.fixture()
def example(monkeypatch, tmp_path):
    monkeypatch.setenv("QQMUSIC_STATE_DIR", str(tmp_path / "mcp-state"))
    monkeypatch.setattr(writes, "account_fingerprint", lambda: "mock-account")
    library = [
        {"directory_id": 201, "playlist_id": 11, "name": "我喜欢", "song_count": 2},
        {"directory_id": 400, "playlist_id": 42, "name": "测试", "song_count": 1},
        {"directory_id": 401, "playlist_id": 43, "name": "空歌单", "song_count": 0},
    ]
    tracks = {
        11: [
            {"mid": "X", "song_id": 100, "type": 0},
            {"mid": "Y", "song_id": 101, "type": 0},
        ],
        42: [{"mid": "X", "song_id": 100, "type": 0}],
        43: [],
    }

    async def list_playlists():
        return [dict(x) for x in library]

    async def list_tracks(pid):
        return [dict(x) for x in tracks[pid]]

    async def likes():
        return {"songs": tracks[11], "playlist": library[0]}

    monkeypatch.setattr(writes, "personal_playlists", list_playlists)
    monkeypatch.setattr(writes, "playlist_tracks", list_tracks)
    monkeypatch.setattr(writes, "liked_songs", likes)

    class FakeBackend:
        async def create_playlist(self, name):
            new_id = max(x["directory_id"] for x in library) + 1
            new_pid = max(tracks) + 1
            library.append(
                {
                    "directory_id": new_id,
                    "playlist_id": new_pid,
                    "name": name,
                    "song_count": 0,
                }
            )
            tracks[new_pid] = []
            return new_id

        async def edit_song(self, action, directory_id, song_id, song_type=0):
            p = next(x for x in library if x["directory_id"] == directory_id)
            lst = tracks[p["playlist_id"]]
            if action == "add":
                lst.append({"mid": "TEST", "song_id": song_id, "type": song_type})
            else:
                lst[:] = [x for x in lst if x["song_id"] != song_id]
            p["song_count"] = len(lst)

        async def delete_playlist(self, directory_id):
            p = next(x for x in library if x["directory_id"] == directory_id)
            if tracks[p["playlist_id"]]:
                raise ValueError("not empty")
            library.remove(p)

    return library, tracks, FakeBackend()
