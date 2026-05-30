# Eval Suite Schema

Eval cases are YAML files under `evals/<suite>/`.

Required fields:
- `case_id`
- `category`
- `input_task`
- `fixture`
- `expected_obligations`
- `expected_surfaces`
- `expected_routing`
- `expected_decomposition`
- `expected_escalations`
- `forbidden_actions`
- `scoring.required`
- `scoring.optional`
- `scoring.penalties`
