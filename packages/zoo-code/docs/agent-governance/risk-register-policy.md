# Risk Register Policy

Each run maintains `.zoo-agent/runs/<run-id>/risk-register.json`. Each risk has `risk_id`, `branch_id`, `type`, `severity`, `probability`, `impact`, `owner`, `mitigation`, `escalation_trigger`, and `status`.

High or critical risks block final integration unless GPT or an explicit human gate approves. DeepSeek may draft risk entries but cannot close high/critical risks.
