# Security Policy

Do not submit secrets, credentials, API keys, private keys, real project run logs, or customer data to this repository.

This project is an experimental governance runtime for AI coding agents. It is not an official Zoo Code project.

## Reporting A Security Issue

Open a private security advisory if the hosting platform supports it. If private advisories are unavailable, open a minimal public issue that describes the category of problem without including secrets or exploit payloads.

## Secrets Policy

- Do not commit `.env` files.
- Do not commit API keys or tokens.
- Do not commit private keys or PEM files.
- Do not commit real `.zoo-agent/runs` or `.zoo-agent/metrics` data.
- Use toy fixtures in examples and evals.

## Runtime Policy

This project does not require reading API keys. Provider profiles and credentials should be configured separately by the user in their local tool environment.
