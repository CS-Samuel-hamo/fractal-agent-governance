# Path Lock Policy

Runtime artifact: `.zoo-agent/runs/<run-id>/path-locks.json`

Path locks bind branch work to `owned_paths`, declared `shared_paths`, and `forbidden_paths`. Parallel branches cannot lock overlapping owned paths. Shared paths must be explicit and require parent-owned integration surface declaration.

Changed files outside owned/shared paths fail the path-lock gate. Security/auth/payment/PII/migration paths cannot be parallelized by DeepSeek; GPT/human gate is required.
