# 我做了一套 AI Coding 的分形治理运行时：让 DeepSeek 写代码、GPT 做裁决，用 Obligation Ledger 防漏改

开源地址：<REPO_URL>

## 1. 背景

我最近在整理一套 AI Coding Agent 的治理方案。核心问题不是“怎么让模型更快写代码”，而是“怎么让模型不要漏掉工程上的隐含工作”。

现在的 AI coding agents 已经能很快生成代码，但真实工程交付并不只等于代码生成。一个改动通常还会牵涉验证、集成、兼容性、安全、架构边界、文档和长期维护。

换句话说：code generation is cheap; verification and integration are still expensive.

## 2. DeepSeek 只做显式需求的问题

我观察到一个常见模式：执行模型很容易只完成用户字面上的任务。

例如用户说：

> Add field `blockedReason` to branch summary.

普通执行可能只会加一个字段，然后认为完成了。

但工程上真正需要考虑的是：

- DTO 是否要更新
- schema/validator 是否要更新
- mapper 是否要更新
- API response 是否要更新
- UI consumer 是否要更新
- fixture 是否要更新
- 是否需要行为测试
- public docs 是否要更新
- 是否保持向后兼容
- 是否需要 rollback note

这就是我想解决的“显式需求”和“隐含义务”之间的差距。

## 3. Obligation Ledger

Obligation Ledger 是这套运行时的核心。

它把任务拆成两类：

- explicit request：用户明确说了什么
- implicit obligations：为了正确完成这件事，系统推导出还必须检查什么

每条 obligation 都有状态：

- required
- maybe
- not_applicable
- deferred
- escalated

这样 agent 不能简单说“done”。它必须说明哪些义务完成了，哪些不适用，哪些延期，哪些需要人类裁决。

## 4. 分形任务治理

复杂任务不是简单拆成一个 flat task list。

我用的是 Controlled Fractal Decomposition：

- root goal 可以分解成 branch
- branch 也可以继续分解
- 但必须有 max_depth
- 每个 branch 有 owned_paths、provides、consumes、acceptance_criteria、exit_condition
- parent branch 负责 aggregation

这套机制的重点不是“多 agent 并行”，而是“受控递归分解”和“父节点汇总裁决”。

## 5. GPT/DeepSeek 路由

我把模型角色分开：

- DeepSeek execution layer：适合做具体实现、批量修改、低风险执行
- GPT decision layer：适合做规划、裁决、审查、升级、父节点汇总

这不是绝对绑定某个模型，而是一种 routing pattern：执行和裁决应该分层。

## 6. Git worktree 并发探索

AI coding 的一个优势是低成本并发探索。

但并发集成很危险。

所以这套运行时使用：

- worktree isolation
- path locks
- merge queue
- final serial integration

例如 docs branch 和 test branch 可以并发探索，但 API branch 可能必须等待 domain branch。共享 type 的修改需要 parent approval。

## 7. 质量门禁和学习闭环

每个 branch 或 run 不能只靠“模型说完成了”。

它需要经过：

- quality gate
- review gate
- integration gate
- fallback/escalation
- eval cases
- learning loop

如果某次 review 发现漏了 obligation，这个结果应该进入学习闭环，影响后续的规则和评估。

## 8. 开源地址

Repo：<REPO_URL>

当前状态是 alpha。它不是 Zoo Code 官方项目，也不是成熟产品。现在更像一个公开实验：把 AI coding agent 的治理运行时结构化出来，让大家可以讨论、测试、批评。

里面包括：

- Zoo Code adapter package
- toy examples
- eval suites
- demo scripts
- launch drafts

## 9. 征求反馈

我想听几类反馈：

- 这种 governance pack 对 AI coding 是否有价值？
- Obligation Ledger 会不会太重？
- 分形任务治理适合哪些复杂度的任务？
- GPT 做裁决、DeepSeek 做执行这个路由是否合理？
- worktree 并发探索应该怎么和实际团队流程结合？
- 如果要适配 Roo/Kilo/Claude/Codex，最小接口应该是什么？

如果你正在做 AI coding workflow、agent runtime、code review automation 或工程平台，我很希望你帮忙看一下。
