# 执行核对清单

## 运行前

- [ ] Codex CLI 已安装：`codex --version`
- [ ] Codex 已登录：`codex login`
- [ ] 已在非业务项目目录打开 Codex App
- [ ] 当前治理包路径已确认，例如 `$env:USERPROFILE\.roo\agent-governance-kit`
- [ ] 已准备好把 `PROMPT_FOR_CODEX_APP.md` 粘贴给 Codex App

## Codex App 执行时

- [ ] dry-run 输出不包含业务项目路径
- [ ] 备份路径已生成
- [ ] validate 通过
- [ ] smoke test 通过
- [ ] install 没有读取 secrets/API keys
- [ ] install 没有自动 merge/push/reset/delete

## 执行后

- [ ] Reload VS Code / Cursor
- [ ] Zoo Code profiles 仍正确：GPT / DeepSeek
- [ ] Launcher 出现 Codex 相关命令
- [ ] Agent Progress Tree 可刷新
- [ ] 用临时测试仓库验证 Codex Task Pack
- [ ] 用 `check_codex_scope.py` 验证越界修改会失败
