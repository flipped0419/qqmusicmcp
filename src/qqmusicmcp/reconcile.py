"""Read-only analysis of uncertain writes: never issues a QQ Music write call."""

from __future__ import annotations


from . import safety
from . import writes
from .writes import _track_snapshot, _digest


async def classify(record: dict) -> str:
    """Compare one durable entry to real current state. No mutation.

    applied / not_applied are evidence categories, not a complete rollback.
    Any unrelated playlist change produces conflict and keeps write blocked.
    """
    if record.get("account") != writes.account_fingerprint():
        return "account_mismatch"
    op = record.get("operation")
    args = record.get("arguments") or {}
    try:
        playlists = await writes.personal_playlists()
        if op == "create_playlist":
            matches = [
                p for p in playlists if (p.get("name") or "") == args.get("name")
            ]
            if len(matches) == 1:
                return "applied"
            return "not_applied" if not matches else "conflict"
        directory_id = args.get("directory_id")
        matches = [p for p in playlists if p.get("directory_id") == directory_id]
        if op == "delete_playlist":
            if not matches:
                return "applied"
            tracks = await _track_snapshot(matches[0])
            return (
                "not_applied"
                if _digest(tracks) == record.get("before_digest")
                else "conflict"
            )
        if op in {"add_song", "remove_song"}:
            if len(matches) != 1:
                return "conflict"
            tracks = await _track_snapshot(matches[0])
            snapshot = _digest(tracks)
            if snapshot == record.get("after_digest"):
                return "applied"
            if snapshot == record.get("before_digest"):
                return "not_applied"
            return "conflict"
        return "conflict"
    except Exception:
        return "unavailable"


async def analyze_unresolved() -> list[dict]:
    items = safety.unresolved_journal(writes.account_fingerprint())
    results = []
    for item in items:
        outcome = await classify(item)
        results.append(
            {
                "operation_id": item["operation_id"],
                "operation": item.get("operation"),
                "journal_status": item["status"],
                "readback_outcome": outcome,
            }
        )
    return results


def mark_resolved(operation_id: str, readback_outcome: str) -> None:
    if readback_outcome not in {"applied", "not_applied"}:
        raise safety.SafetyError("ambiguous write cannot be marked resolved")
    record = safety._read_json(safety.journal_path(operation_id))
    if record.get("account") != writes.account_fingerprint() or record.get(
        "status"
    ) not in {"in_flight", "uncertain"}:
        raise safety.SafetyError(
            "record is not an unresolved operation for this account"
        )
    safety.update_journal(
        operation_id,
        "reconciled_applied"
        if readback_outcome == "applied"
        else "reconciled_not_applied",
    )
