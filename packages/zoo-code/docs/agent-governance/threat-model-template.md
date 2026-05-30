# Threat Model Template

## Assets
Data, credentials, user permissions, service availability.

## Trust Boundaries
API boundary, auth boundary, database boundary, third-party boundary.

## Threats
authz bypass, input validation failure, injection, SSRF, XSS, path traversal, destructive command, dependency supply-chain risk.

## Required Controls
validation, authorization, least privilege, logging without secrets, rollback, monitoring.
