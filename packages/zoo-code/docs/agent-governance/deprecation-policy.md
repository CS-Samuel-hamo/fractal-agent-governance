# Deprecation Policy

Assets enter deprecation candidate state when:
- a skill is `irrelevant` five consecutive invocations
- a rule repeatedly produces false positives
- a lesson is older than 90 days and has not recurred
- a project local rule conflicts with project profile
- a script gate blocks repeatedly and reviewers grant repeated human exceptions

Deprecation does not delete automatically. Curator-draft may propose deprecation. GPT curator approves. Security, human exception, and model routing deprecations need human approval.
