# Learning Trigger Policy

Learning is event-driven, not step-driven.

Do not create lessons for every successful task. Do not update skills for every ordinary failure.

Create a lesson candidate only for:

- scope violation
- test failure not fixed after retry
- review BLOCKER or MAJOR
- repeated same failure type
- human correction
- architecture violation
- Codex changed denied files
- Codex inferred architecture change without approval

Lesson candidates require GPT curator or human approval. Machine-detectable problems should become scripts or gates before they become long prompts. Low-risk one-time issues are recorded as events only.
