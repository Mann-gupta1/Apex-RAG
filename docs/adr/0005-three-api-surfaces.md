# ADR 0005 — Coexisting REST, gRPC, and GraphQL surfaces

**Status**: Accepted
**Date**: 2026-05-08

## Context

Different consumers want different things:
- The **Next.js UI** is happiest with JSON-over-REST and SSE for chat.
- **Internal services** (e.g. a downstream summariser) need low-overhead,
  strongly-typed, bidirectional streams.
- **Future frontends or partner integrations** want flexible queries and
  federation — i.e. GraphQL.

## Decision

Ship **all three** surfaces, mounted side-by-side. Implementation:
- **FastAPI** (REST + SSE) hosts `/api/*` and shares the process with Strawberry GraphQL at `/graphql`.
- **gRPC** (`grpcio`) runs on a separate worker (`:50051`) so a slow tool call
  can't starve HTTP. Proto file at `proto/apex.proto`.

## Rationale

- Each surface exposes the same backend functions; no business logic
  duplication.
- gRPC bidi is the cleanest way to surface chat streams to internal services
  without proxying SSE.
- GraphQL costs us ~150 lines and unlocks federation-ready partner
  integrations later.

## Consequences

- Three sets of tests. We compensate with shared Pydantic models in
  `apex.schemas` so wire formats track each other.
- gRPC stubs are codegen artefacts (`make proto`); they live in
  `src/apex/api/apex_pb2*.py` and are .gitignored.
- The runbook treats the gRPC worker as a separate failure domain.
