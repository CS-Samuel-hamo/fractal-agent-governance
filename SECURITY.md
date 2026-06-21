# Security

Agent Runtime is local-first.

## Public Alpha Safety Boundaries

- No GitHub API calls.
- No automatic push.
- No automatic merge.
- No remote PR creation.
- No remote GitHub release creation.
- No production deployment.
- No `.env` content reading.
- No API key or token reading.
- No raw backend log publishing.

## Reporting Security Issues

Please do not open public issues containing secrets, tokens, credentials, private keys, or proprietary source. Open a minimal report that describes:

- affected command
- expected behavior
- actual behavior
- whether secrets/logs were removed
- sanitized environment details

## Safe Sharing

`.zoo-agent/` artifacts are local runtime artifacts. Share them only after review and sanitization.

## Scope

This alpha does not provide enterprise governance, hosted telemetry, cloud sync, account management, or remote execution policy controls.
