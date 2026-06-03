# Architecture Boundaries Schema

Path: `.zoo-agent/architecture-boundaries.json`.

Architecture boundaries describe allowed dependency direction and module layer assignments. The file may start as a low-confidence draft from `generate-project-map.py`, then be refined by GPT planner/reviewer or the user.

```json
{
  "schema_version": "1.0",
  "generated_by": "generate-project-map.py",
  "project_root": "",
  "status": "draft|approved|unknown",
  "confidence": "low|medium|high",
  "layers": [
    {
      "layer": "domain",
      "allowed_to_depend_on": [],
      "notes": "Pure domain should avoid IO/env/network/UI."
    }
  ],
  "module_layer_assignments": [
    {
      "module_id": "src/api",
      "layer": "api_ui",
      "confidence": "heuristic"
    }
  ],
  "unknowns": []
}
```

Rules:

- DeepSeek may draft boundaries but must not approve high-risk architecture decisions.
- Unknown boundaries block high-risk or multi-module architecture changes unless GPT planner/reviewer explicitly accepts the risk.
- Local code style rules may reference architecture boundaries, but they must not replace the boundary map.
