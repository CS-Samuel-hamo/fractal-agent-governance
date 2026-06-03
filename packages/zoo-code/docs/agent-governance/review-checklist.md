# Review Checklist

## 1. Contract fidelity
- [ ] Objective satisfied.
- [ ] Non-goals not violated.
- [ ] Edge cases covered.
- [ ] Error behavior defined and tested.

## 2. Integration surfaces
- [ ] API/interface updated.
- [ ] Caller sites updated.
- [ ] route/task/command/branch dispatch updated.
- [ ] registry/factory/provider/DI updated.
- [ ] enum/constants/types updated or explicitly not applicable.
- [ ] DTO/schema/validator/mapper updated or explicitly not applicable.
- [ ] exports/index updated.
- [ ] docs/config/migration/telemetry updated or explicitly not applicable.

## 3. Existing pattern alignment
- [ ] Similar features searched.
- [ ] Existing utilities/enums/processors reused or non-reuse justified.
- [ ] No duplicate abstraction introduced.

## 4. Proc / Processor data-source handling
- [ ] Data-source difference explicitly modeled.
- [ ] Old source behavior preserved.
- [ ] New source behavior tested.
- [ ] Registration/call chain uses correct source.

## 5. Governance event trigger
Create an event for `agent-integrator` if a BLOCKER/MAJOR finding reveals a repeatable process failure that may require governance curation.
