"""Human approval, audit, crash, and recovery tests use fake data only."""

from __future__ import annotations
import json
import pytest

from qqmusicmcp import safety, writes, reconcile


def test_preview_cannot_be_applied_by_ai_without_external_approval(
    example, monkeypatch
):
    import asyncio

    async def run():
        monkeypatch.setenv("QQMUSIC_ENABLE_WRITES", "true")
        monkeypatch.setattr(writes, "probe_valid", lambda: True)
        gate = writes.WriteGate(example[2])
        preview = await gate.preview("create_playlist", name="守卫测试")
        with pytest.raises(safety.SafetyError, match="not been independently approved"):
            await gate.apply(preview["confirmation_token"])
        assert len(example[0]) == 3
        assert safety.list_journal() == []

    asyncio.run(run())


def test_approval_is_exact_one_time_and_account_bound(example, monkeypatch):
    import asyncio

    async def run():
        monkeypatch.setenv("QQMUSIC_ENABLE_WRITES", "true")
        monkeypatch.setattr(writes, "probe_valid", lambda: True)
        gate = writes.WriteGate(example[2])
        p = await gate.preview("create_playlist", name="新建目标")
        account = "mock-account"
        other = {"name": "偷偷改名", "operation": "create_playlist"}
        with pytest.raises(safety.SafetyError):
            safety.consume_approval(
                p["confirmation_token"], account, "create_playlist", other, None, None
            )
        with pytest.raises(safety.SafetyError):
            safety.describe_preview(p["confirmation_token"], "other-account")
        safety.approve_preview(p["confirmation_token"], account)
        with pytest.raises(safety.SafetyError):
            safety.approve_preview(p["confirmation_token"], account)
        success = await gate.apply(p["confirmation_token"])
        assert success["status"] == "verified"
        with pytest.raises(ValueError):
            await gate.apply(p["confirmation_token"])
        audit = safety.list_journal()
        assert len(audit) == 1 and audit[0]["status"] == "verified"

    asyncio.run(run())


@pytest.mark.asyncio
async def test_network_failure_logs_uncertain_and_blocks_retries(example, monkeypatch):
    monkeypatch.setenv("QQMUSIC_ENABLE_WRITES", "true")
    monkeypatch.setattr(writes, "probe_valid", lambda: True)

    class FailedBackend:
        async def create_playlist(self, name):
            raise TimeoutError("secret-simulated-response-value")

    gate = writes.WriteGate(FailedBackend())
    p = await gate.preview("create_playlist", name="失败目标")
    safety.approve_preview(p["confirmation_token"], "mock-account")
    with pytest.raises(safety.SafetyError, match="outcome uncertain"):
        await gate.apply(p["confirmation_token"])
    item = safety.unresolved_journal("mock-account")
    assert len(item) == 1 and item[0]["status"] == "uncertain"
    assert item[0]["reason"] == "TimeoutError"
    assert "secret-simulated-response-value" not in json.dumps(item)
    gate2 = writes.WriteGate(example[2])
    with pytest.raises(safety.SafetyError, match="unresolved prior write"):
        await gate2.preview("create_playlist", name="后续")
    checks = await reconcile.analyze_unresolved()
    assert checks[0]["readback_outcome"] == "not_applied"
    reconcile.mark_resolved(checks[0]["operation_id"], "not_applied")
    assert not safety.unresolved_journal("mock-account")
    p2 = await gate2.preview("create_playlist", name="可继续")
    assert p2["status"] == "preview_only"


def test_expired_and_untrusted_approvals_are_rejected(example, monkeypatch):
    import time

    monkeypatch.setenv("QQMUSIC_ENABLE_WRITES", "true")
    ticket = "example-token-long-enough"
    safety.issue_preview(
        ticket,
        "mock-account",
        "create_playlist",
        {"operation": "create_playlist", "name": "Demo"},
        None,
        None,
        time.time() - 10,
    )
    with pytest.raises(safety.SafetyError, match="expired"):
        safety.describe_preview(ticket, "mock-account")
    ticket2 = "another-example-token-long"
    safety.issue_preview(
        ticket2,
        "mock-account",
        "create_playlist",
        {"operation": "create_playlist", "name": "Demo"},
        None,
        None,
        time.time() + 120,
    )
    path = safety._approval_path(ticket2)
    path.chmod(0o644)
    with pytest.raises(safety.SafetyError, match="unsafe"):
        safety.describe_preview(ticket2, "mock-account")


@pytest.mark.asyncio
async def test_reconcile_refuses_conflict(example, monkeypatch):
    monkeypatch.setenv("QQMUSIC_ENABLE_WRITES", "true")
    monkeypatch.setattr(writes, "probe_valid", lambda: True)

    class MutatesThenFails:
        async def edit_song(self, action, directory_id, song_id, song_type=0):
            playlist = next(p for p in example[0] if p["directory_id"] == directory_id)
            tracks = example[1][playlist["playlist_id"]]
            tracks.append({"song_id": 9999, "type": 0, "mid": "EXTERNAL"})
            playlist["song_count"] = len(tracks)
            raise TimeoutError("unknown outcome")

    gate = writes.WriteGate(MutatesThenFails())
    p = await gate.preview("add_song", directory_id=400, song_id=101)
    safety.approve_preview(p["confirmation_token"], "mock-account")
    with pytest.raises(safety.SafetyError):
        await gate.apply(p["confirmation_token"])
    checks = await reconcile.analyze_unresolved()
    assert checks[0]["readback_outcome"] == "conflict"
    with pytest.raises(safety.SafetyError):
        reconcile.mark_resolved(checks[0]["operation_id"], "conflict")
    assert safety.unresolved_journal("mock-account")


@pytest.mark.asyncio
async def test_ambiguous_backend_may_have_applied_write(example, monkeypatch):
    """A write that succeeded remotely but timed out is not retried."""
    monkeypatch.setenv("QQMUSIC_ENABLE_WRITES", "true")
    monkeypatch.setattr(writes, "probe_valid", lambda: True)

    class AppliedThenTimeout:
        async def edit_song(self, action, directory_id, song_id, song_type=0):
            playlist = next(p for p in example[0] if p["directory_id"] == directory_id)
            tracks = example[1][playlist["playlist_id"]]
            tracks.append({"song_id": song_id, "type": song_type, "mid": "MID"})
            playlist["song_count"] = len(tracks)
            raise TimeoutError("simulated timeout AFTER remote application")

    gate = writes.WriteGate(AppliedThenTimeout())
    ticket = await gate.preview("add_song", directory_id=400, song_id=101)
    safety.approve_preview(ticket["confirmation_token"], "mock-account")
    with pytest.raises(safety.SafetyError, match="outcome uncertain"):
        await gate.apply(ticket["confirmation_token"])
    entries = await reconcile.analyze_unresolved()
    assert entries[0]["readback_outcome"] == "applied"
    assert len(safety.unresolved_journal("mock-account")) == 1
    reconcile.mark_resolved(entries[0]["operation_id"], "applied")
    assert not safety.unresolved_journal("mock-account")


def test_crashed_in_flight_record_blocks_new_mutations(example, monkeypatch):
    import asyncio

    async def scenario():
        monkeypatch.setenv("QQMUSIC_ENABLE_WRITES", "true")
        monkeypatch.setattr(writes, "probe_valid", lambda: True)
        safety.new_journal(
            "f" * 64,
            "mock-account",
            "create_playlist",
            {"operation": "create_playlist", "name": "crashed"},
            None,
            None,
        )
        gate = writes.WriteGate(example[2])
        with pytest.raises(safety.SafetyError, match="unresolved prior write"):
            await gate.preview("create_playlist", name="another")

    asyncio.run(scenario())


def test_lock_prevents_simultaneous_process_writes(example):
    with safety.exclusive_write_lock():
        with pytest.raises(safety.SafetyError, match="another write operation"):
            with safety.exclusive_write_lock():
                pass
