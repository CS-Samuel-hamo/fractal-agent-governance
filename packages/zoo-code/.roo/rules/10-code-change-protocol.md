# Code Change Protocol

## Before Editing
1. Locate analogous implementations.
2. Locate all integration surfaces.
3. Locate existing shared types/enums/utilities.
4. Locate relevant tests and fixtures.
5. Produce an Impact Map.

Suggested searches:
```bash
rg "FeatureName|SimilarFeature|DomainTerm" .
rg "enum .*Domain|Domain.*Enum|type .*Domain|interface .*Domain" src test .
rg "register|route|handler|processor|task|branch|factory|provider|adapter" src test .
rg "Proc|Processor|Handler|Service|Repository|Mapper|Validator" src test .
```

## During Editing
- Prefer modifying existing extension points over duplicating logic.
- Preserve backwards compatibility unless the contract explicitly says otherwise.
- Keep data-source changes explicit and testable.
- Add or update tests in the same pattern as analogous features.

## After Editing
Run checks in this order:
1. Formatter/linter for touched files, if available.
2. Typecheck/static diagnostics.
3. Targeted tests.
4. Broader regression suite when the change touches shared interfaces, routing, persistence, auth, or task orchestration.

## Completion Evidence
Return files changed, integration surfaces updated, existing patterns reused, tests/checks run, acceptance mapping, and risks/follow-ups.
