# Demo Walkthrough

1. Open `root-goal.json` to show a single user-facing feature goal.
2. Open `branch-tree.yaml` and show the bounded branch tree.
3. Point out `owned_paths`, `provides`, and `consumes` for each branch.
4. Open `parent-aggregation-matrices.md` and explain that the parent does not just concatenate child results. It checks coverage, dependencies, ownership, risk, and integration order.
5. Open `branch-state-example.json` to show a branch waiting for a dependency instead of guessing.

Key message:

Fractal decomposition is useful only when recursion is controlled. The parent branch owns depth, dependency aggregation, and final integration.
