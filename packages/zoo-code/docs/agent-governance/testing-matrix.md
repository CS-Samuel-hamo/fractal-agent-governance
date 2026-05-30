# Testing Matrix

| Change Type | Required Test |
|---|---|
| pure logic | unit |
| API request/response | integration |
| auth/permission | positive and negative tests |
| UI workflow | e2e or component interaction |
| migration | migration test and rollback notes |
| parser/state machine | property-based where available |
| stable generated output | golden |
| Proc/Processor data-source mismatch | old-source and new-source behavior tests |

Do not use existence-only tests as behavior tests.
