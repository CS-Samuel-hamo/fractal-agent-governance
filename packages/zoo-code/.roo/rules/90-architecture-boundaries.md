# Architecture Boundaries

Respect project architecture. If unclear, record `unknown`; do not invent architecture.

Default dependency direction: domain -> no IO/env/network/API/UI; application -> domain and ports; infrastructure -> implements ports; API/UI -> adapt external input to application.

Do not bypass services to access repositories unless the project profile allows it. Respect monorepo package boundaries and public exports.

Use `.zoo-agent/project-map.json` for module/file ownership facts and `.zoo-agent/architecture-boundaries.json` for dependency direction and layer assignments. If changed files do not map to a known module, or a dependency crosses an unknown boundary, stop for project-map refresh or GPT planner/reviewer decision.
