# Security policy — Alpha

This is an experimental, unofficial bridge to personal QQ Music accounts. It is
not audited, and the unofficial web API may change. Do not expose this service
or its trusted approval terminal as an unauthenticated public endpoint.

## Supported versions

There is **no supported stable release**. The `main` branch and pre-release
`0.1.0a1` are for testing and development; security fixes may change APIs.

## Reporting security issues

Please use GitHub's **private vulnerability reporting** feature for the
repository when available. Otherwise contact the repository maintainer
privately before posting a public reproduction. Never include real credentials,
Cookie headers, personally identifiable details, or private playlist content.

## Credential and write threat model

- Store QQ Music API Key and session Cookie only in a private mode `0600`
  credential file or a securely supplied process environment. The account
  Cookie is equivalent to a sensitive login credential.
- `QQMUSIC_ENABLE_WRITES` defaults to false. A long-lived one-time probe proof
  is a protocol compatibility record, **not** an authorization to do any write.
- Every write requires an independent **host-local, interactive** approval tied
  to the exact preview token, operation and account; do not grant untrusted MCP
  callers shell access that can run `scripts/approve_write.py`.
- Preflight and postflight readback checks, cross-process write locks and
  durable audit records reduce risk; they do **not** provide atomic rollback.
- After uncertain outcomes, the daemon blocks writes until operator-driven
  read-only reconciliation. Do not retry unknown writes automatically.
- `My Likes` and non-empty playlist deletion are protected. No heart toggling
  or multi-song batch operations exist in this release.
- Privileged host users (and any software allowed to execute arbitrary shell
  commands as the MCP account) can access or alter the local approval files.
  No software-only safeguard survives compromise of that trust boundary.

This library does not store passwords, tokens, or Cookies in Git or include a
remote unauthenticated HTTP server. Tunnel and reverse proxy deployments must
supply their own access control and follow least privilege.
