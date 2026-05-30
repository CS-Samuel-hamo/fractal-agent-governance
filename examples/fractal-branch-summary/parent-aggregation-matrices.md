# Parent Aggregation Matrices

## Objective Coverage Matrix

| Objective | Domain | API | Tests | Docs | Status |
| --- | --- | --- | --- | --- | --- |
| Represent summary counts | owns | consumes | verifies | documents | covered |
| Preserve compatibility | informs | owns | verifies | documents | covered |
| Avoid scheduling changes | constrains | constrains | verifies | documents | covered |

## Dependency Matrix

| Branch | Depends on | Reason | Parent action |
| --- | --- | --- | --- |
| domain | root | needs success criteria | start first |
| api | domain | needs summary contract | wait |
| test | domain, api | needs behavior and contract | start after contracts stabilize |
| docs | api | needs final public shape | can draft, finalize after API |

## Ownership Matrix

| Path group | Owner branch | Shared? | Approval |
| --- | --- | --- | --- |
| `toy-app/domain/*` | domain | no | branch owner |
| `toy-app/api/*` | api | no | branch owner |
| `toy-app/fixtures/*` | test | yes | parent approval |
| `docs/*` | docs | no | branch owner |

## Risk Matrix

| Risk | Branch | Level | Mitigation |
| --- | --- | --- | --- |
| API compatibility break | api | medium | optional field and contract test |
| Domain/API coupling | domain, api | medium | mapper boundary review |
| Fixture drift | test | low | fixture ownership note |
| Documentation overclaim | docs | low | docs review against final contract |

## Integration Matrix

| Integration step | Inputs | Gate | Result |
| --- | --- | --- | --- |
| Domain merge | domain branch | quality gate | domain contract ready |
| API merge | domain + api | review gate | response contract ready |
| Test merge | domain + api + test | quality gate | behavior verified |
| Docs merge | final contract + docs | review gate | public note ready |
