# Backend

Python/FastAPI application. The target package is `app/`, with `contracts/`, `evidence/`, `intelligence/` and `api/` modules. `main.py` serves HTTP; `worker.py` runs durable jobs; `bootstrap.py` wires concrete adapters. PostgreSQL is canonical and Qdrant is a rebuildable index.

See [codebase architecture](../docs/implementation/architecture.md) for the full tree and import rules, and [worker ownership](../docs/implementation/README.md) before editing. Dependency manifests, entry points and application code are not implemented yet. This folder establishes the backend boundary, not a runnable service.
