# Governance Regression Policy

Any change to `.roo/rules*`, `.roo/skills*`, `.roo/commands*`, `scripts/*gate*`, model routing policy, human exception policy, or security policy must have regression evidence.

Required regression fields:
- `before_behavior`
- `expected_new_behavior`
- `regression_prompt`
- `pass_condition`
- `rollback_condition`

No regression means the governance change cannot be installed. A regression may be a prompt, fixture, static script check, smoke test, or local governance validate target.
