# Leaf Task Contract

Leaf contracts live under `.zoo-agent/runs/<run-id>/leaf-tasks/`.

Each leaf records objective, task type, risk, owned resources, allowed/denied files, provides/consumes, acceptance, test policy, rollback note, preferred route, readiness reference, and execution mode.

Codex task packs may only be generated from leaf tasks that pass the task readiness gate.
