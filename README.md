# qqmusicmcp

A unified **QQ Music MCP server** for Linux, built with Python 3.11+ and the MCP Python SDK. It combines the [official Tencent Music QQ Music Skill](https://github.com/tencentmusic/qqmusic-skills) HTTP APIs with optional personal-library tools based on unofficial web endpoints.

The MCP server uses **stdio** and runs under a local MCP client or a separately configured transport/tunnel. It does not require a particular VPS provider, hosting platform, desktop environment, or public inbound port.

## Features

| Feature | Source | Status |
| --- | --- | --- |
| Song, artist, album, and playlist search | Official QQ Music Skill API v0.0.3 | Working; requires API Key |
| Daily recommendations, radio, charts, public playlists, listening reports | Official Skill | Working; requires API Key |
| Read personal playlists and “My Likes” | Unofficial QQ Music web APIs | Working with an authenticated browser session; experimental |
| Resolve song MID to numeric song ID/type | Unofficial song detail API | Read-only |
| Create a playlist, add/remove a song, delete an empty playlist | Unofficial web APIs | Implemented, guarded by explicit opt-in; write protocol tested with a temporary playlist |
| Modify “My Likes” / change liked-song hearts | — | **Not supported** |
| Automatic rollback and batch playlist editing | — | Not yet implemented |

Unofficial APIs may change or be restricted by QQ Music without notice. The AI interpretation endpoint uses SSE and is not yet implemented here.

## Requirements and installation

- Linux with Python **3.11 or later**
- [uv](https://docs.astral.sh/uv/)
- Network access to the QQ Music official and web APIs

```bash
git clone https://github.com/flipped0419/qqmusicmcp.git
cd qqmusicmcp
uv sync --extra test
uv run pytest -q
```

Start the stdio MCP server with your MCP client or run it directly:

```bash
uv run qqmusicmcp
```

Configure the client's command to run `uv run qqmusicmcp` with its working directory set to this repository (or invoke the installed executable by absolute path). Standard output is reserved for MCP messages.

If your host sets a global `PYTHONPATH` that injects incompatible packages, launch with `env -u PYTHONPATH uv run qqmusicmcp`. This is an **environment-specific workaround**, not a requirement of Linux or this project.

## Credentials

The official API Key and the optional QQ Music browser session Cookie are independent credentials.

- Create an official API Key from [QQ Music Skill](https://y.qq.com/n/ryqq_v2/qqmusic_skills).
- For personal-library access, log into [QQ Music](https://y.qq.com/) in your browser, then find the authenticated request's **Cookie header value** in your browser's Network developer tools. A Cookie grants access to your account: keep it private, and rotate/revoke it if exposed.

The following scripts must run in a trusted **interactive Linux terminal** and will hide the value being entered:

```bash
uv run python scripts/configure_api_key.py
uv run python scripts/configure_cookie.py
```

The default private credentials file is **outside the source tree**:

- When running from a source checkout: `../.qqmusicmcp/credentials.json` (relative to the repository root).
- When running an installed package: `${XDG_STATE_HOME:-~/.local/state}/qqmusicmcp/credentials.json`.
- To choose a different location, set `QQMUSIC_SECRETS_FILE` to the desired absolute file path.

The scripts use directory mode `0700` and file mode `0600`. You can also supply `QQMUSIC_API_KEY` and `QQMUSIC_COOKIE` through your process environment; these override the stored values. **Never commit keys, Cookies, access tokens, or private login records to Git.** Credentials in a private file are still accessible to a privileged host administrator.

### Read-only verification

The script below prints only status and counts, never your credentials, song names, or account ID:

```bash
uv run python scripts/test_personal_read.py
```

In your MCP client, call `qqmusic_status` to check which providers are configured without exposing secrets. For song metadata used by playlist-write tools, call `qqmusic_search` first, then `qqmusic_resolve_song_mid` with a selected result's `songMid`.

## Playlist writes and safety

Writing to QQ Music is **disabled by default**, even when personal-library reading works.

Normal write operations require all of the following:

1. An operator explicitly starts the MCP process with `QQMUSIC_ENABLE_WRITES=true`.
2. A **one-time successful account/protocol capability proof** exists. This proof does not expire merely because time passes.
3. An individual operation is prepared with `qqmusic_preview_write` and then executed with its one-use, five-minute `confirmation_token` through `qqmusic_apply_write`. Before changing an existing playlist, the target state is read again; results are verified by reading again after the write.

The proof is bound to the authenticated account and known write protocol version. If either changes, writes are blocked until compatibility is investigated.

**Do not repeat the test probe for routine writes.** The probe creates, edits, and deletes a temporary playlist; QQ Music may retain deleted test playlists in its recovery history. An already validated account only needs its existing proof.

For a *first-time installation*, a human may explicitly authorize a one-off test in an interactive terminal:

```bash
QQMUSIC_ENABLE_WRITES=true uv run python scripts/test_write_probe.py
```

Read and confirm its prompt before proceeding: the script really changes the account and may leave a disposable playlist behind if cleanup fails.

To upgrade a successful record created by older versions **without touching QQ Music**, run:

```bash
uv run python scripts/migrate_probe.py
```

The explicit write flag remains off unless you enable it for the running MCP process. Never leave it enabled in a publicly reachable, unauthenticated service. A preview ticket checks state and limits replay; **it does not prove that a human approved the request**. Require explicit user approval in the connecting MCP client before sensitive operations.

The “My Likes” directory (ID `201`) is protected against direct edits and deletion. Non-empty playlist deletion is prohibited. Automatic rollback, cross-process tickets, and batch transactions have **not** been implemented, so treat any uncertain write outcome as requiring a read-only inspection before attempting again.

## Sources and licensing

- [tencentmusic/qqmusic-skills](https://github.com/tencentmusic/qqmusic-skills) — Apache-2.0. Official HTTP protocol implemented from published Skill documentation.
- [baoozak/qqmusic-mcp](https://github.com/baoozak/qqmusic-mcp) — MIT. Unofficial personal-library and write protocol adapted here; upstream MIT notice is preserved at `src/qqmusicmcp/vendor/LICENSE.baoozak`.
- [L-1124/QQMusicApi](https://github.com/L-1124/QQMusicApi) — GPL-3.0-or-later. Evaluated but **not** copied or imported into this project.

This software is intended for authorized personal use. Follow QQ Music's terms of service, rate limits, copyright restrictions, and applicable law.
