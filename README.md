# qqmusicmcp

Unified QQ Music MCP (Python / Linux / stdio), deployed and tested on QwenPaw.

## Features

Official Tencent Music Skill 0.0.3 API: search (songs/albums/playlists/MVs/artists), daily mix, radio, AI playlist suggestions, charts, chart detail, public playlist detail, listening reports.

Optional third-party personal library: list personal playlists, read playlist songs, export My Likes using a session cookie. **Unofficial API; may break when QQ Music changes.**

Write planning: preview only. **No account mutation is implemented in v0.1.0, regardless of flags.** The next milestone is a disposable-playlist probe + verified writes + rollback.

## Install and run

```bash
uv sync --extra test
uv run pytest -q
uv run qqmusicmcp
```

Run in an environment without external `PYTHONPATH` that injects conflicting MCP versions (on QwenPaw: `env -u PYTHONPATH uv run ...`). `qqmusicmcp` uses stdio; a local MCP supervisor or Secure Tunnel starts it. Nothing listens publicly.

Set `QQMUSIC_API_KEY` in the server's private environment (get one at https://y.qq.com/n/ryqq_v2/qqmusic_skills). `QQMUSIC_COOKIE` is optional for personal library reading. **Do not share any key, Cookie, or Tunnel secret in chat or commit to Git.** `QQMUSIC_ENABLE_WRITES=false` is the safe default.

## Sources

- Tencent Music official [qqmusic-skills](https://github.com/tencentmusic/qqmusic-skills) (Apache-2.0): independently implemented protocol per v0.0.3 docs.
- [baoozak/qqmusic-mcp](https://github.com/baoozak/qqmusic-mcp) (MIT): reading protocol is adapted in `library.py`. Original Windows authentication is not used.
- [L-1124/QQMusicApi](https://github.com/L-1124/QQMusicApi) (GPL-3.0-or-later): evaluated, not copied/imported in this version.

The official AI interpretation endpoint is SSE and not included yet. Respect QQ Music's rate limits, terms of service and music copyright.

## Configure the official API key on QwenPaw

Open an **interactive terminal** on the QwenPaw host, then execute:

```bash
cd /app/working/shellmcp-workspace/qqmusicmcp
env -u PYTHONPATH uv run python scripts/configure_api_key.py
```

The script prompts for the key without echoing it. It refuses non-interactive input and stores the key in a mode `0600` file under `/app/working/shellmcp-workspace/.qqmusicmcp/credentials.json` on the persistent volume, **outside the public Git checkout**. The service loads this key automatically; the `QQMUSIC_API_KEY` environment variable overrides it. Never paste your key into GitHub, a chat, a command argument, or a web log. Anyone with root access to the host can still access the file; the script is only intended to prevent accidental disclosure.

Once set, run `env -u PYTHONPATH uv run qqmusicmcp` from the repo directory or use a supervising MCP client. Real API queries require this key, while personal library reads require a separate authenticated session.

## Connect your personal library (read-only)

The Tencent Skill API Key does **not** grant browser-session access to personal playlist-management endpoints. This optional feature requires a QQ Music **browser Cookie** (sensitive account credential). Never paste it into ChatGPT or GitHub.

1. On your own desktop, sign into [QQ Music](https://y.qq.com/) in the browser. Open Developer Tools (F12), Network, reload the page, select an authenticated request to `y.qq.com` or `c.y.qq.com`. Under Request Headers, copy **only the value** of the `Cookie` header. Do not copy the whole request, and never share it online. You may need to use a desktop browser to access the site.
2. Open an interactive terminal on your trusted QwenPaw server and run:

```bash
cd /app/working/shellmcp-workspace/qqmusicmcp
env -u PYTHONPATH uv run python scripts/configure_cookie.py
```

3. Paste the Cookie once at the hidden terminal prompt. It is stored in the existing mode 0600 private credentials file **outside the repository**.
4. To test without showing song names, Cookie, or account ID:

```bash
env -u PYTHONPATH uv run python scripts/test_personal_read.py
```

This flow accesses undocumented QQ Music web endpoints, which may reject browser cookies from a different IP, require renewed authentication, or stop functioning. It does **not** enable account writes.


## Experimental guarded playlist writes (not yet production-verified)

Only operations on *ordinary personal playlists* are supported: create, add a song, remove a song, delete an **empty** playlist. `My Likes` (directory 201) is protected against mutations. This API is unofficial and may break without warning.

All writes are disabled unless **all three** conditions hold:

1. The MCP server is started with `QQMUSIC_ENABLE_WRITES=true` (default **false**).
2. A person runs `env -u PYTHONPATH uv run python scripts/test_write_probe.py` in an **interactive terminal** and explicitly types the full confirmation phrase. The probe will **temporarily create a playlist, add a song from My Likes, verify, remove it, then delete the temporary playlist**. This really modifies the QQ Music account, so ask permission before running it. It may leave a temporary playlist behind if cleanup fails.
3. The recent successful probe (valid for 15 minutes) is followed by a 5-minute one-use preview ticket from `qqmusic_preview_write`, then `qqmusic_apply_write`. The target playlist is re-read before applying and the result is verified via another read. No batch changes or persistent rollback are implemented yet.

**Do not run the probe or set the write flag just to perform read-only testing.** The test suite only uses mocks and never calls real write endpoints.

Technical attribution: `src/qqmusicmcp/write_backend.py` adapts the account-write protocol from [baoozak/qqmusic-mcp](https://github.com/baoozak/qqmusic-mcp) under MIT (see `src/qqmusicmcp/vendor/LICENSE.baoozak`). No GPL-licensed source is incorporated.

## Searching songs for the write tools

`qqmusic_search_library_songs(keyword, page=1)` queries the QQ Music website's undocumented search endpoint and returns `song_id` and `song_type` needed for playlist additions. This is read-only and separate from the official Skill search. It has only been mock-tested until validated against the authenticated user's session.
