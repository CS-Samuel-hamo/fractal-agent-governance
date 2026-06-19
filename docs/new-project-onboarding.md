# New Project Onboarding

In an empty directory:

```powershell
agent bootstrap
```

Bootstrap initializes git and creates:

- `README.md`
- `AGENTS.md`
- `.gitignore`
- `.zoo-agent/project-profile.json`
- `.zoo-agent/project-readiness.json`
- `.zoo-agent/bootstrap-report.md`
- `.zoo-agent/bootstrap.lock`
- `.zoo-agent/TASKS.md`

It does not generate business modules or choose a complex technology stack.

New project safety rules:

- Empty directories may be initialized with `git init`.
- Bootstrap does not create an initial commit by default.
- If bootstrap commit support is enabled later, it must add only explicit generated bootstrap files, never `git add all`.
- Non-empty non-git directories are not initialized unless `--new` or `--force-new-project` is passed.
- Business modules are not generated unless the user asks for a bounded task after bootstrap.

If a directory is non-empty and is not a git repo, bootstrap does not initialize git unless you explicitly pass:

```powershell
agent bootstrap --new
```

or:

```powershell
agent bootstrap --force-new-project
```

No automatic commit is performed.
