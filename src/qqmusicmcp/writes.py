"""Write safety. v0.1.0 is strictly preview-only: no account mutations."""
import os
import secrets
import time

def writes_enabled():
    return os.getenv("QQMUSIC_ENABLE_WRITES", "").lower() == "true"

class WriteGate:
    def __init__(self):
        self.tickets = {}

    def preview(self, operation, name="", directory_id=0, song_id=0):
        if operation not in {"create_playlist", "add_song", "remove_song", "delete_playlist"}:
            raise ValueError("unknown write operation")
        if operation != "create_playlist" and directory_id <= 0:
            raise ValueError("directory_id required")
        if directory_id == 201:
            raise ValueError("My Likes mutations disabled")
        if operation == "create_playlist" and (not name.strip() or len(name) > 80):
            raise ValueError("invalid playlist name")
        if operation in {"add_song", "remove_song"} and song_id <= 0:
            raise ValueError("song_id required")
        args = {"operation": operation, "name": name,
                "directory_id": directory_id, "song_id": song_id}
        ticket = secrets.token_urlsafe(24)
        self.tickets[ticket] = (time.monotonic()+300, args)
        return {"status": "preview_only", "confirmation_token": ticket,
                "expires_in_seconds": 300, "changes": args,
                "message": "No write occurred; applying writes is not supported in this version"}

    def apply(self, ticket):
        raise PermissionError("writes disabled: probe, write verification and rollback not yet implemented")
