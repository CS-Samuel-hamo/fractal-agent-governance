# Installation

This project uses a global install approach for the Zoo Code adapter.

Do not copy the adapter into business repositories.

Recommended sequence:

1. Run validation.
2. Review installer behavior.
3. Use dry-run behavior where supported.
4. Install globally.
5. Reload VS Code / Zoo Code.
6. Configure provider profiles separately.

The global package lives outside business projects. A business project receives only local governance artifacts such as:

- `.zoo-agent/project-profile.json`
- `.zoo-agent/project-map.json`
- `.zoo-agent/current-run.json`
- `.zoo-agent/TASKS.md`
- `AGENTS.md` or `AGENTS.md.new`
- `.roo/rules/*.md`
- `.gitignore.agent.patch` when ignore rules need review

Run project bootstrap from a project root:

```powershell
python <global-kit>\scripts\bootstrap_project.py --project . --mode auto --apply
```

Bootstrap does not overwrite existing complete local rules. It writes `.new` or `.patch` files when a human merge decision is required.
