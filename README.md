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
