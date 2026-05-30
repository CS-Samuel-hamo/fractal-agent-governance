# Demo Script: Fractal Decomposition

## Target Audience

Agent orchestration researchers, maintainers of multi-agent coding systems, and senior engineers reviewing complex agent changes.

## 2 Minute Version

1. Open `examples/fractal-branch-summary/root-goal.json`.
2. Show that the goal spans domain, API, tests, and docs.
3. Open `branch-tree.yaml`.
4. Point to owned paths, provides, consumes, and exit conditions.
5. Open `parent-aggregation-matrices.md` and show that the parent branch owns integration.

Core line:

This is not a list of subtasks. It is controlled recursive decomposition with parent aggregation.

## 5 Minute Version

1. Explain why naive parallel subtasks fail on shared contracts.
2. Show bounded recursion with `max_depth`.
3. Walk branch by branch through the tree.
4. Use the dependency matrix to show why API waits for domain.
5. Use the ownership matrix to show how shared fixtures or types require approval.
6. End with the integration matrix and final parent gate.

## Files To Show

- `examples/fractal-branch-summary/root-goal.json`
- `examples/fractal-branch-summary/branch-tree.yaml`
- `examples/fractal-branch-summary/parent-aggregation-matrices.md`
- `examples/fractal-branch-summary/branch-state-example.json`

## Core Innovation To Emphasize

- Controlled Fractal Decomposition has depth limits.
- Branches declare ownership and dependencies.
- Parent aggregation checks coverage, risk, ownership, and integration order.

## Call To Action

Run the eval case `evals/fractal-decomposition/cases/api-ui-feature.yaml` against an agent and check whether it creates governed branches or only a flat task list.
