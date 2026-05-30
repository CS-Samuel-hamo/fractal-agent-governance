# Security Governance

Changes involving auth, authorization, payment, PII, credentials, production config, database migration, destructive operation, or external network access require GPT final review or human gate. Secret files, `.env`, private keys, tokens, and provider profiles must not be read, copied, or printed.

Security obligations in the Obligation Ledger require a security gate. Ordinary human exception is insufficient for auth/payment/PII risk; explicit high-risk approval is required.
