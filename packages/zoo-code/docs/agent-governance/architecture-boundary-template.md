# Architecture Boundary Template

| Layer | Owns | May depend on | Must not depend on |
|---|---|---|---|
| domain | business rules | domain primitives | env, IO, network, DB, API, UI |
| application | use cases | domain, ports | concrete infra unless local pattern allows |
| infrastructure | DB/network/files | application ports, domain types | UI |
| api | request/response | application | repository internals |
| ui | user interaction | API/client contracts | DB |

Record service bypass, repository access, env access, monorepo boundary, shared type/export impact, generated files, and exceptions. Unknown stays `unknown`.
