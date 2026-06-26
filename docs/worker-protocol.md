# Worker Protocol v1.0

> 结构化上下文交换协议——让 AI Worker 理解项目全景，返回结构化结果，自动更新项目状态。

## 概述

Worker Protocol 定义了 AI Project Operator 和 AI Worker（Claude CLI、Codex CLI 等）之间的交互契约。它让 Worker 不再只是"执行一个 prompt 返回 stdout"，而是：

1. **接收项目上下文** — 项目地图、模块状态、风险登记册、当前目标
2. **执行任务** — 按收到的上下文执行
3. **返回结构化结果** — 告诉 Operator 改了哪些文件、发现了什么风险、下一步该做什么
4. **Operator 自动更新** — 项目地图版本化更新、风险追加、下一步建议同步

## 协议流程

```
Operator                          Worker
  │                                 │
  ├─ 1. build_context_prompt() ────→│  注入项目全景
  │                                 │
  │  2. build_protocol_instruction()│
  │  ──────────────────────────────→│  要求结构化输出
  │                                 │
  │  3. 执行任务                     │
  │                                 │
  │  4. ←── 返回结构化结果 ──────────│  JSON block
  │                                 │
  │  5. parse_worker_output()        │
  │  6. apply_worker_result()        │
  │  7. 自动更新项目地图             │
  │                                 │
```

## 协议格式

### 输入：项目上下文

Operator 在发送给 Worker 的 prompt 前，注入一个结构化的上下文块：

```
<project-context>
  <modules>
    <module name="auth" status="refactored"/>
    <module name="api" status="working"/>
  </modules>
  <risks>
    <risk severity="high">XSS vulnerability in login form</risk>
  </risks>
  <goal>实现用户认证系统</goal>
</project-context>
```

### 输入：结构化输出要求

在 prompt 末尾，Operator 附加以下指令：

```
<!-- ZOO-AGENT-PROTOCOL -->
IMPORTANT: After completing the task, output a structured result block:

```json
{
  "protocol_version": "1.0",
  "summary": "Brief summary of what was done",
  "changed_files": ["path/to/file1", "path/to/file2"],
  "new_risks": [
    {"description": "Risk description", "severity": "low|medium|high"}
  ],
  "modules_affected": ["module-name"],
  "suggested_next": "Suggested next action for the project",
  "blockers": ["Any blockers encountered"]
}
```
<!-- /ZOO-AGENT-PROTOCOL -->
```

### 输出：Worker 返回结果

Worker 在完成任务的回复末尾，需要包含上述 JSON 块。Operator 会从回复中提取并解析。

## 结构化结果字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `protocol_version` | string | 是 | 当前为 `"1.0"` |
| `summary` | string | 是 | 做了什么（200 字以内） |
| `changed_files` | string[] | 否 | 修改过的文件路径列表 |
| `new_risks` | object[] | 否 | 新发现的风险 |
| `new_risks[].description` | string | 是 | 风险描述 |
| `new_risks[].severity` | string | 是 | `low`, `medium`, `high` |
| `modules_affected` | string[] | 否 | 受影响的模块 ID |
| `suggested_next` | string | 否 | 建议的下一步动作 |
| `blockers` | string[] | 否 | 遇到的阻塞项 |

## 交班协议（Handoff）

当一个 Worker 完成任务但项目尚未完成（需要另一个 Worker 接替）时，输出交班信息：

```json
{
  "protocol_version": "1.0",
  "handoff": {
    "work_done": [
      {"file": "auth.py", "summary": "重构了 login 函数"}
    ],
    "remaining": ["需要写测试", "需要更新文档"],
    "key_insights": ["utils.py 中的 validate_token 函数需要修改"],
    "decisions_made": ["改用 JWT 替代 Session"],
    "warnings": ["config.py 中的 SECRET_KEY 是硬编码的"]
  }
}
```

## Worker 实现示例

### Claude CLI

```bash
# Operator 内部执行的命令
claude --print \
  --model claude-sonnet-4-6 \
  "<project-context>
   <modules>...</modules>
   </project-context>

   ## Task

   修复 README 中的过期链接

   <!-- ZOO-AGENT-PROTOCOL -->
   After completing, output structured JSON...
   <!-- /ZOO-AGENT-PROTOCOL -->"
```

### Codex CLI

```bash
# Operator 内部执行的命令
codex --model gpt-4o \
  "<project-context>
   ...
   </project-context>

   ## Task

   ...

   <!-- ZOO-AGENT-PROTOCOL -->
   ...
   <!-- /ZOO-AGENT-PROTOCOL -->"
```

### 自定义脚本

任何可以接受 stdin/stdout 的脚本都可以作为 Worker：

```python
#!/usr/bin/env python3
"""Custom Worker example."""
import json, sys

# 读取上下文（来自 stdin 或命令行参数）
context = json.loads(sys.argv[1])

# 执行任务
result = do_something()

# 输出结构化结果
output = {
    "protocol_version": "1.0",
    "summary": "完成了自定义任务",
    "changed_files": result["files"],
    "new_risks": result.get("risks", []),
}
print(f"<!-- ZOO-AGENT-PROTOCOL -->\n{json.dumps(output)}\n<!-- /ZOO-AGENT-PROTOCOL -->")
```

## 协议版本与兼容性

- 当前版本：`1.0`
- 向后兼容：新增字段不破坏旧版本解析器
- 解析器行为：未知字段被忽略，缺失的必填字段降级为空值

## 参考实现

- `scripts/worker_protocol.py` — Python 参考实现
- `scripts/worker_claude_code.py` — Claude CLI 适配器
