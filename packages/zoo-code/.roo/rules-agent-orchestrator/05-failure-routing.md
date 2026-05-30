# Failure Routing

Project profile unknown -> profiler retry then planner. Quality gate fail -> executor. Mechanical review fail -> executor. Semantic BLOCKER/MAJOR -> curator event plus planner reconsideration. Parent aggregation fail -> branch-manager. Dependency conflict -> branch-manager. Path ownership violation -> branch-manager. Integration conflict -> integrator. Security/auth/payment/PII -> stop plus human gate. Install dry-run unsafe -> stop install.
