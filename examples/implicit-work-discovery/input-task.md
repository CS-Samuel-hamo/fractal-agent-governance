# Input Task

Add field `blockedReason` to branch summary.

Context:

- The project exposes a branch summary object through an API.
- Some branches can be blocked by an external condition.
- Existing clients should keep working if the field is missing or null.

Constraints:

- Do not change unrelated branch lifecycle behavior.
- Preserve backward compatibility.
- Add tests only around the new field propagation.
