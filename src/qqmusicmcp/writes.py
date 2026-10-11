"""Write transactions for third-party QQ Music API.

All live writes require both an explicit server flag AND a recent probe completed
by a human in a TTY. A tool-call-only AI cannot initiate the probe.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from .library import personal_playlists, playlist_tracks, liked_songs, read_cookie, uin_from_cookie
from .secrets_config import credentials_path
from .write_backend import WriteBackend

LIKED_DIRECTORY_ID = 201
PROBE_TTL_SECONDS = 900
PREVIEW_TTL_SECONDS = 300

def writes_enabled() -> bool:
    return os.getenv('QQMUSIC_ENABLE_WRITES', '').strip().lower() == 'true'

def proof_path() -> Path:
    return credentials_path().parent / 'write_probe.json'

def account_fingerprint() -> str:
    return hashlib.sha256(uin_from_cookie(read_cookie()).encode('ascii')).hexdigest()

def probe_valid() -> bool:
    if not writes_enabled():
        return False
    path = proof_path()
    try:
        if path.is_symlink() or path.stat().st_mode & 0o077:
            return False
        item = json.loads(path.read_text(encoding='utf-8'))
        return (item.get('account') == account_fingerprint() and
                item.get('expires_at', 0) > time.time() and item.get('schema') == 1)
    except (OSError, ValueError, TypeError, KeyError):
        return False

def _save_probe() -> None:
    """Store only the expiry and a one-way account fingerprint, never secrets."""
    path = proof_path()
    if path.is_symlink():
        raise PermissionError('unsafe probe path')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    import tempfile
    fd, name = tempfile.mkstemp(prefix='.write-probe-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump({'schema': 1, 'account': account_fingerprint(),
                       'expires_at': time.time() + PROBE_TTL_SECONDS}, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def _track_ids(tracks: list[dict]) -> set[tuple[int, int]]:
    ids: set[tuple[int, int]] = set()
    for track in tracks:
        try:
            song_id = int(track.get('song_id', 0))
            song_type = int(track.get('type', 0))
        except (TypeError, ValueError):
            continue
        if song_id > 0:
            ids.add((song_id, song_type))
    return ids

def _digest(tracks: list[dict]) -> str:
    data = sorted(_track_ids(tracks))
    return hashlib.sha256(json.dumps(data, separators=(',', ':')).encode('ascii')).hexdigest()

async def _find_playlist(directory_id: int) -> dict:
    for item in await personal_playlists():
        if item['directory_id'] == directory_id:
            return item
    raise ValueError('directory ID not found in the authenticated account')

async def _track_snapshot(playlist: dict) -> list[dict]:
    pid = playlist.get('playlist_id')
    if not pid:
        raise ValueError('playlist has no public playlist_id')
    tracks = await playlist_tracks(int(pid))
    count = playlist.get('song_count')
    if count is not None and len(tracks) < int(count):
        raise ValueError('playlist data appears truncated; refuse writes')
    return tracks

async def _eventually(condition, *, retries: int = 5):
    for attempt in range(retries):
        value = await condition()
        if value is not None:
            return value
        if attempt != retries - 1:
            await asyncio.sleep(1)
    raise RuntimeError('QQ Music write could not be confirmed by a fresh read')

@dataclass
class Preview:
    operation: str
    args: dict
    expires_at: float
    expected_digest: str | None = None
    target_name: str | None = None

class WriteGate:
    def __init__(self, backend: WriteBackend | None = None):
        self.tickets: dict[str, Preview] = {}
        self.lock = asyncio.Lock()
        self.backend = backend or WriteBackend()

    async def preview(self, operation: str, name: str = '', directory_id: int = 0,
                      song_id: int = 0, song_type: int = 0):
        if operation not in {'create_playlist', 'add_song', 'remove_song', 'delete_playlist'}:
            raise ValueError('unknown write operation')
        args = {'operation': operation}
        fingerprint = None
        target = None
        if operation == 'create_playlist':
            if not name.strip() or len(name) > 80:
                raise ValueError('invalid playlist name')
            if any((p.get('name') or '').casefold() == name.strip().casefold()
                   for p in await personal_playlists()):
                raise ValueError('playlist name already exists; choose a distinct name')
            args['name'] = name.strip()
        else:
            if directory_id <= 0 or directory_id == LIKED_DIRECTORY_ID:
                raise ValueError('cannot edit My Likes or an invalid directory')
            playlist = await _find_playlist(directory_id)
            target = playlist.get('name')
            tracks = await _track_snapshot(playlist)
            fingerprint = _digest(tracks)
            args['directory_id'] = directory_id
            if operation == 'delete_playlist':
                if tracks:
                    raise ValueError('refuse to delete a non-empty playlist')
            else:
                if song_id <= 0 or song_type < 0:
                    raise ValueError('numeric song ID and type required')
                selected = (song_id, song_type)
                ids = _track_ids(tracks)
                if operation == 'add_song' and selected in ids:
                    raise ValueError('song already belongs to target playlist')
                if operation == 'remove_song' and selected not in ids:
                    raise ValueError('song not found in target playlist')
                args.update(song_id=song_id, song_type=song_type)
        ticket = secrets.token_urlsafe(28)
        self.tickets[ticket] = Preview(operation, args, time.monotonic()+PREVIEW_TTL_SECONDS,
                                       fingerprint, target)
        return {'status': 'preview_only', 'confirmation_token': ticket,
                'expires_in_seconds': PREVIEW_TTL_SECONDS,
                'operation': operation, 'changes': args, 'target_name': target,
                'writes_enabled': writes_enabled(), 'probe_passed': probe_valid(),
                'note': 'No mutation occurred. Applying requires an enabled server flag, '
                        'a recent locally approved probe and a fresh target-state check.'}

    async def apply(self, confirmation_token: str):
        async with self.lock:
            preview = self.tickets.pop(confirmation_token, None)
            if preview is None or preview.expires_at < time.monotonic():
                raise ValueError('confirmation token invalid, expired or already used')
            if not writes_enabled() or not probe_valid():
                raise PermissionError('server write flag or recent locally approved probe missing')
            op, args = preview.operation, preview.args
            if op == 'create_playlist':
                name = args['name']
                if any((p.get('name') or '').casefold() == name.casefold()
                       for p in await personal_playlists()):
                    raise ValueError('playlist already exists; preview again')
                new_id = await self.backend.create_playlist(name)
                async def check_new():
                    try:
                        return await _find_playlist(new_id)
                    except ValueError:
                        return None
                await _eventually(check_new)
                return {'status': 'verified', 'operation': op, 'directory_id': new_id}
            playlist = await _find_playlist(args['directory_id'])
            if playlist.get('name') != preview.target_name:
                raise ValueError('playlist identity changed; preview again')
            tracks = await _track_snapshot(playlist)
            if _digest(tracks) != preview.expected_digest:
                raise ValueError('playlist changed after preview; operation cancelled')
            if op == 'delete_playlist':
                if tracks:
                    raise ValueError('refuse to delete a non-empty playlist')
                await self.backend.delete_playlist(args['directory_id'])
                async def check_deleted():
                    items = await personal_playlists()
                    return True if not any(p['directory_id'] == args['directory_id'] for p in items) else None
                await _eventually(check_deleted)
            else:
                action = 'add' if op == 'add_song' else 'remove'
                song = (args['song_id'], args['song_type'])
                await self.backend.edit_song(action, args['directory_id'], *song)
                async def check_track():
                    recent = await _track_snapshot(await _find_playlist(args['directory_id']))
                    present = song in _track_ids(recent)
                    return True if present == (action == 'add') else None
                await _eventually(check_track)
            return {'status': 'verified', 'operation': op, 'directory_id': args['directory_id']}

async def run_temporary_probe(backend: WriteBackend | None = None) -> dict:
    """Called only from an interactive local CLI with explicit human approval."""
    if not writes_enabled():
        raise PermissionError('QQMUSIC_ENABLE_WRITES is not true; no mutation performed')
    backend = backend or WriteBackend()
    all_liked = (await liked_songs())['songs']
    candidate = next((s for s in all_liked if str(s.get('song_id') or '').isdigit()
                      and int(s['song_id']) > 0 and s.get('mid')), None)
    if not candidate:
        raise RuntimeError('no suitable track to safely test in a disposable playlist')
    song_id, song_type = int(candidate['song_id']), int(candidate.get('type') or 0)
    name = 'qqmusicmcp-test-' + secrets.token_hex(4)
    created_id: int | None = None
    cleaned = False
    stage = 'create'
    try:
        created_id = await backend.create_playlist(name)
        async def get_created():
            try: return await _find_playlist(created_id)
            except ValueError: return None
        item = await _eventually(get_created)
        stage = 'add'
        await backend.edit_song('add', created_id, song_id, song_type)
        async def check_added():
            current = await _track_snapshot(await _find_playlist(created_id))
            return True if (song_id, song_type) in _track_ids(current) else None
        await _eventually(check_added)
        stage = 'remove'
        await backend.edit_song('remove', created_id, song_id, song_type)
        async def check_removed():
            current = await _track_snapshot(await _find_playlist(created_id))
            return True if (song_id, song_type) not in _track_ids(current) else None
        await _eventually(check_removed)
        stage = 'delete'
        await backend.delete_playlist(created_id)
        async def check_deleted():
            items = await personal_playlists()
            return True if not any(p['directory_id'] == created_id for p in items) else None
        await _eventually(check_deleted)
        cleaned = True
        _save_probe()
        return {'status': 'passed', 'temporary_playlist_cleaned': True,
                'expires_in_seconds': PROBE_TTL_SECONDS}
    finally:
        if created_id is not None and not cleaned:
            # Best-effort cleanup, without ever touching a pre-existing playlist.
            try:
                created = await _find_playlist(created_id)
                current = await _track_snapshot(created)
                if (song_id, song_type) in _track_ids(current):
                    await backend.edit_song('remove', created_id, song_id, song_type)
                    await asyncio.sleep(1)
                    current = await _track_snapshot(await _find_playlist(created_id))
                if not current:
                    await backend.delete_playlist(created_id)
            except Exception:
                # Caller must inspect the temporary playlist if cleanup fails.
                pass
