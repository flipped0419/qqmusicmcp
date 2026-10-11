# Contributing

This is an **Experimental / Alpha** project. Bug reports, code reviews and
carefully scoped pull requests are welcome.

Before contributing:

1. Read [SECURITY.md](SECURITY.md), especially the write approval and Cookie
   handling expectations.
2. Fork/branch from `main`. Work with dummy credentials and mocked HTTP
   responses; **never test a PR against another person's account**.
3. Run `uv sync --extra test`, `uv run pytest -q`, and
   `uv tool run --from ruff==0.14.7 ruff check --select E4,E7,E9,F src scripts tests`.
4. Update README and test fixtures when a tool or permission model changes.
5. Document the provenance and license of any third-party code. Do not add
   GPL-licensed code without discussing redistribution implications.

Pull requests involving live playlist mutation must include tests proving
read-only-by-default, exact independent approval, no replays, write journaling
and failure-closed behavior. Submit security vulnerabilities privately.

No real QQ Music credentials, account IDs, personal track lists, or server-specific
private paths should appear in the public repository or CI logs.
