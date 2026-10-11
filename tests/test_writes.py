"""Mocks only. This test suite never reaches QQ Music production endpoints."""

from __future__ import annotations
import json
import pytest
from qqmusicmcp import writes
from qqmusicmcp.write_backend import csrf_token


def test_csrf_token_matches_expected():
    assert csrf_token("p_skey=abc") == csrf_token("uin=o123; p_skey=abc")
    assert csrf_token("") == 5381


@pytest.mark.asyncio
async def test_preview_does_not_write_or_modify_likes(example):
    _, tracks, backend = example
    gate = writes.WriteGate(backend)
    with pytest.raises(ValueError, match="My Likes"):
        await gate.preview("remove_song", directory_id=201, song_id=100)
    with pytest.raises(ValueError, match="non-empty"):
        await gate.preview("delete_playlist", directory_id=400)
    previous = list(tracks[42])
    preview = await gate.preview("remove_song", directory_id=400, song_id=100)
    assert preview["status"] == "preview_only"
    assert tracks[42] == previous


@pytest.mark.asyncio
async def test_apply_disabled_by_default(example, monkeypatch):
    _, _, backend = example
    monkeypatch.delenv("QQMUSIC_ENABLE_WRITES", raising=False)
    gate = writes.WriteGate(backend)
    preview = await gate.preview("create_playlist", name="新建")
    with pytest.raises(PermissionError):
        await gate.apply(preview["confirmation_token"])


@pytest.mark.asyncio
async def test_create_add_remove_delete_verified(example, monkeypatch):
    library, tracks, backend = example
    monkeypatch.setenv("QQMUSIC_ENABLE_WRITES", "true")
    monkeypatch.setattr(writes, "probe_valid", lambda: True)
    gate = writes.WriteGate(backend)
    a = await gate.preview("create_playlist", name="新建")
    from qqmusicmcp import safety

    safety.approve_preview(a["confirmation_token"], "mock-account")
    done = await gate.apply(a["confirmation_token"])
    directory_id = done["directory_id"]
    b = await gate.preview("add_song", directory_id=directory_id, song_id=101)
    safety.approve_preview(b["confirmation_token"], "mock-account")
    assert (await gate.apply(b["confirmation_token"]))["status"] == "verified"
    c = await gate.preview("remove_song", directory_id=directory_id, song_id=101)
    safety.approve_preview(c["confirmation_token"], "mock-account")
    assert (await gate.apply(c["confirmation_token"]))["status"] == "verified"
    d = await gate.preview("delete_playlist", directory_id=directory_id)
    safety.approve_preview(d["confirmation_token"], "mock-account")
    assert (await gate.apply(d["confirmation_token"]))["status"] == "verified"
    assert all(x["directory_id"] != directory_id for x in library)


@pytest.mark.asyncio
async def test_refuse_stale_preview_and_replay(example, monkeypatch):
    library, tracks, backend = example
    monkeypatch.setenv("QQMUSIC_ENABLE_WRITES", "true")
    monkeypatch.setattr(writes, "probe_valid", lambda: True)
    gate = writes.WriteGate(backend)
    ticket = await gate.preview("remove_song", directory_id=400, song_id=100)
    from qqmusicmcp import safety

    safety.approve_preview(ticket["confirmation_token"], "mock-account")
    tracks[42].append({"mid": "Y", "song_id": 101, "type": 0})
    library[1]["song_count"] += 1
    with pytest.raises(ValueError, match="changed after preview"):
        await gate.apply(ticket["confirmation_token"])
    with pytest.raises(ValueError, match="already used"):
        await gate.apply(ticket["confirmation_token"])


@pytest.mark.asyncio
async def test_probe_mock_disposable_playlist(example, monkeypatch, tmp_path):
    library, tracks, backend = example
    monkeypatch.setenv("QQMUSIC_ENABLE_WRITES", "true")
    called = []
    monkeypatch.setattr(writes, "probe_valid", lambda: False)
    monkeypatch.setattr(writes, "_save_probe", lambda: called.append("success"))
    result = await writes.run_temporary_probe(backend)
    assert result["status"] == "passed"
    assert called == ["success"]
    assert len(library) == 3
    assert len(tracks[11]) == 2


@pytest.mark.asyncio
async def test_no_probe_without_flag(example, monkeypatch):
    monkeypatch.delenv("QQMUSIC_ENABLE_WRITES", raising=False)
    with pytest.raises(PermissionError):
        await writes.run_temporary_probe(example[2])


def test_migrate_expired_legacy_probe_without_remote_writes(tmp_path, monkeypatch):
    import time

    path = tmp_path / "write_probe.json"
    monkeypatch.setattr(writes, "proof_path", lambda: path)
    monkeypatch.setattr(writes, "account_fingerprint", lambda: "same-account")
    old = {"schema": 1, "account": "same-account", "expires_at": time.time() - 60}
    path.write_text(json.dumps(old))
    path.chmod(0o600)
    assert not writes.probe_valid()
    assert writes.migrate_legacy_probe() == "migrated_without_new_probe"
    assert writes.probe_valid()
    record = json.loads(path.read_text())
    assert record["schema"] == 2
    assert "expires_at" not in record
    assert record["protocol"] == writes.PROBE_PROTOCOL


def test_probe_record_is_account_and_protocol_bound(tmp_path, monkeypatch):
    path = tmp_path / "write_probe.json"
    monkeypatch.setattr(writes, "proof_path", lambda: path)
    monkeypatch.setattr(writes, "account_fingerprint", lambda: "my-account")
    writes._save_probe()
    assert writes.probe_valid()
    monkeypatch.setattr(writes, "account_fingerprint", lambda: "another-account")
    assert not writes.probe_valid()
    monkeypatch.setattr(writes, "account_fingerprint", lambda: "my-account")
    monkeypatch.setattr(writes, "PROBE_PROTOCOL", "musicu-playlist-v2")
    assert not writes.probe_valid()


def test_untrusted_world_readable_probe_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / "write_probe.json"
    monkeypatch.setattr(writes, "proof_path", lambda: path)
    monkeypatch.setattr(writes, "account_fingerprint", lambda: "account")
    writes._save_probe()
    path.chmod(0o644)
    assert not writes.probe_valid()


@pytest.mark.asyncio
async def test_repeated_probe_skips_without_qqmusic_mutation(example, monkeypatch):
    _, _, backend = example
    monkeypatch.setenv("QQMUSIC_ENABLE_WRITES", "true")
    monkeypatch.setattr(writes, "probe_valid", lambda: True)

    class RefuseAnyWrite:
        async def create_playlist(self, name):
            raise AssertionError("must not write")

        async def edit_song(self, *args):
            raise AssertionError("must not write")

        async def delete_playlist(self, *args):
            raise AssertionError("must not write")

    result = await writes.run_temporary_probe(RefuseAnyWrite())
    assert result["status"] == "already_verified"
