# Frontend

Separate TypeScript browser application with its own dependency manifest, build and interaction tests. Source belongs under `src/`; feature modules cover authentication, documents, search, chat, source receipts, administration and the visualization entry point.

Use backend HTTP APIs and generated OpenAPI types. Do not access SQL, Qdrant or model providers directly or include private keys in browser assets. See [codebase architecture](../docs/implementation/architecture.md) and [Worker C](../docs/implementation/worker-c-product.md). Application code and build tooling are not implemented yet.
