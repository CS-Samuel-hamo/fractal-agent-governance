# New Project Demo

Use an empty temporary directory:

```powershell
agent bootstrap --workspace <empty-temp-dir>
agent "fix typo in README" --workspace <empty-temp-dir> --dry-run
```

Expected:

- git is initialized
- README and AGENTS are created
- runtime files are created under `.zoo-agent`
- no business module code is generated
