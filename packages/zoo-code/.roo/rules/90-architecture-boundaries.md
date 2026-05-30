# Architecture Boundaries

Respect project architecture. If unclear, record `unknown`; do not invent architecture.

Default dependency direction: domain -> no IO/env/network/API/UI; application -> domain and ports; infrastructure -> implements ports; API/UI -> adapt external input to application.

Do not bypass services to access repositories unless the project profile allows it. Respect monorepo package boundaries and public exports.
