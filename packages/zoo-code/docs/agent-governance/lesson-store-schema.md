# Lesson Store Schema

Lesson index path: `.zoo-agent/lessons/lesson-index.json`

Lesson path: `.zoo-agent/lessons/<lesson-id>.json`

Required fields:
- `lesson_id`
- `source_event_id`
- `run_id`
- `branch_id`
- `failure_type`
- `symptom`
- `root_cause`
- `recurrence_count`
- `scope`: `global|project|language|framework|mode`
- `recommended_asset`: `none|rule|skill|script|local-rule|project-profile|adr`
- `proposed_change`
- `expected_behavior_change`
- `regression_prompt`
- `regression_check`
- `rollback_plan`
- `confidence`
- `status`: `candidate|approved|installed|rejected|deprecated`
- `owner_mode`
- `approved_by`
- `installed_at`

Lessons with status `approved` or `installed` must have regression evidence. Lessons that affect security, human exception, model routing, release risk, or data policy must include human approval reference.
