# 自我进化纠错闭环

## 目标

让项目管理体系从真实失败中改进，但避免规则无限膨胀、误伤效率或让执行模型自己改宪法。

## 闭环

```text
event -> postmortem -> failure taxonomy -> rule change proposal
      -> governance patch -> regression prompt/check -> validation -> recurrence tracking
```

## 触发条件

- reviewer 给出 BLOCKER/MAJOR。
- 用户指出 agent 漏了接口、分支、枚举、工具类、Proc 数据源差异。
- 分支状态与实际 diff 不一致。
- 集成时发现多个 child branch 语义冲突。
- 同类小问题连续出现两次。

## 防失控原则

1. curator 只能改治理文件，不能改产品代码。
2. 每个规则变更必须绑定 event id。
3. 规则必须带来可观察行为：搜索、清单、输出字段、测试、门禁。
4. 不能用“更认真”“多思考”作为规则。
5. 每个变更必须有 rollback 说明。
6. 每月或每 N 个任务回顾一次 governance bloat。
