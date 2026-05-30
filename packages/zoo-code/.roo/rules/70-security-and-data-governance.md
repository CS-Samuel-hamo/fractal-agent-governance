# Security And Data Governance

Do not read, print, copy, export, or modify secrets, `.env`, credentials, API keys, tokens, private keys, or provider profiles. Do not automatically modify credential or production config files.

Changes involving auth, authorization, payment, PII, credentials, production config, database migration, destructive operation, or external network access require GPT final review or human gate. Check input validation, SQL/NoSQL injection, SSRF, XSS, path traversal, dependency supply-chain risk, and destructive command risk.

Security/auth/payment/PII risk cannot be bypassed by ordinary exception. It requires explicit high-risk approval with rollback and monitoring.
