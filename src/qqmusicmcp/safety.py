"""Local human approval and crash-safe write journal for the experimental MCP.

The MCP protocol exposes no tool that can approve a write. An operator must
inspect and approve the exact preview in a separate trusted terminal.
Approval is an OS file-permission boundary, not protection from host root.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time

from .secrets_config import credentials_path


class SafetyError(RuntimeError):
    """Write denied or awaiting independent human review."""


def state_root() -> Path:
    value = os.getenv("QQMUSIC_STATE_DIR")
    return Path(value).expanduser() if value else credentials_path().parent


def ensure_private_dir(path: Path) -> Path:
    # mkdir(parents=True) uses normal umask on ancestors. Explicitly create
    # and validate the state root before any child directory.
    root = state_root()
    if path != root and root in path.parents:
        ensure_private_dir(root)
    if path.is_symlink():
        raise SafetyError("refusing a symlinked private state directory")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not stat.S_ISDIR(path.lstat().st_mode) or path.stat().st_mode & 0o077:
        raise SafetyError("private state directory requires mode 0700")
    return path


def _atomic_json(path: Path, data: dict) -> None:
    ensure_private_dir(path.parent)
    if path.is_symlink():
        raise SafetyError("refusing a symlinked private state file")
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(data, target, ensure_ascii=False, separators=(",", ":"))
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
        # Persist the rename before any remote write.
        parent_fd = os.open(path.parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read_json(path: Path) -> dict:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise SafetyError("unsafe permissions on private state file")
        if path.parent.stat().st_mode & 0o077:
            raise SafetyError("unsafe permissions on private state directory")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SafetyError("invalid private state record")
        return data
    except (OSError, ValueError):
        raise SafetyError("private state record is unavailable or invalid") from None


def ticket_hash(ticket: str) -> str:
    if not isinstance(ticket, str) or not 20 <= len(ticket) <= 160:
        raise SafetyError("invalid confirmation token")
    return hashlib.sha256(ticket.encode("utf-8")).hexdigest()


def _approval_path(ticket: str) -> Path:
    return state_root() / "approvals" / (ticket_hash(ticket) + ".json")


def issue_preview(
    ticket: str,
    account: str,
    operation: str,
    arguments: dict,
    expected_digest: str | None,
    target_name: str | None,
    expires_at: float,
) -> None:
    payload = {
        "schema": 1,
        "account": account,
        "operation": operation,
        "arguments": arguments,
        "expected_digest": expected_digest,
        "target_name": target_name,
        "expires_at": expires_at,
        "status": "pending",
    }
    _atomic_json(_approval_path(ticket), payload)


def describe_preview(ticket: str, account: str) -> dict:
    record = _read_json(_approval_path(ticket))
    if record.get("schema") != 1 or record.get("account") != account:
        raise SafetyError("approval does not match this account")
    if record.get("expires_at", 0) < time.time():
        raise SafetyError("approval token expired; create a new preview")
    if record.get("status") not in {"pending", "approved"}:
        raise SafetyError("approval token is no longer pending")
    return record


def approve_preview(ticket: str, account: str) -> None:
    record = describe_preview(ticket, account)
    if record["status"] != "pending":
        raise SafetyError("approval already submitted")
    record["status"] = "approved"
    record["approved_at"] = time.time()
    _atomic_json(_approval_path(ticket), record)


def consume_approval(
    ticket: str,
    account: str,
    operation: str,
    arguments: dict,
    expected_digest: str | None,
    target_name: str | None,
) -> None:
    record = describe_preview(ticket, account)
    if (
        record.get("status") != "approved"
        or record.get("operation") != operation
        or record.get("arguments") != arguments
        or record.get("expected_digest") != expected_digest
        or record.get("target_name") != target_name
    ):
        raise SafetyError("this exact operation has not been independently approved")
    record["status"] = "consumed"
    _atomic_json(_approval_path(ticket), record)


def journal_dir() -> Path:
    return state_root() / "write_journal"


def journal_path(operation_id: str) -> Path:
    if (
        not isinstance(operation_id, str)
        or len(operation_id) != 64
        or any(c not in "0123456789abcdef" for c in operation_id)
    ):
        raise SafetyError("invalid audit operation id")
    return journal_dir() / (operation_id + ".json")


def new_journal(
    operation_id: str,
    account: str,
    operation: str,
    arguments: dict,
    before_digest: str | None,
    after_digest: str | None,
) -> None:
    record = {
        "schema": 1,
        "operation_id": operation_id,
        "account": account,
        "operation": operation,
        "arguments": arguments,
        "before_digest": before_digest,
        "after_digest": after_digest,
        "status": "in_flight",
        "started_at": time.time(),
    }
    path = journal_path(operation_id)
    if path.exists() or path.is_symlink():
        raise SafetyError("audit id already exists")
    _atomic_json(path, record)


def update_journal(operation_id: str, status: str, *, reason: str = "") -> None:
    if status not in {
        "verified",
        "uncertain",
        "reconciled_applied",
        "reconciled_not_applied",
    }:
        raise ValueError("invalid audit journal status")
    path = journal_path(operation_id)
    record = _read_json(path)
    record["status"] = status
    record["updated_at"] = time.time()
    if reason:
        # Only an exception type, never an exception message with response data.
        record["reason"] = reason[:64]
    _atomic_json(path, record)


def list_journal() -> list[dict]:
    root = journal_dir()
    if not root.exists():
        return []
    if root.is_symlink() or root.stat().st_mode & 0o077:
        raise SafetyError("unsafe journal directory permissions")
    return [_read_json(p) for p in sorted(root.glob("*.json"))]


def unresolved_journal(account: str) -> list[dict]:
    return [
        x
        for x in list_journal()
        if x.get("account") == account and x.get("status") in {"in_flight", "uncertain"}
    ]


@contextmanager
def exclusive_write_lock():
    path = state_root() / "write.lock"
    ensure_private_dir(path.parent)
    if path.is_symlink():
        raise SafetyError("unsafe write lock path")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(fd).st_mode & 0o077:
            raise SafetyError("unsafe write lock file permissions")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SafetyError("another write operation is running") from None
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
