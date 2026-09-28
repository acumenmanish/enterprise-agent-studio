# Enterprise Agent Studio — Local Scheduling MVP

Local-first prototype for the v0.3 architecture, focused on the first
production use case: a printing production-scheduling agent. The portable
agent manifest is the configuration source; the Studio uses synthetic
printing data, a deterministic OR-Tools optimizer, hard-constraint checks,
planner approval, and an append-only Postgres run-event log.

The model gateway uses the portable OpenAI-compatible chat-completions
contract and is optional. With no model settings,
the app runs locally and generates a deterministic explanation. A configured
hosted model is used only to explain an already-computed schedule; it does not
make scheduling decisions or bypass validation/approval.

## Run locally

Requirements: Docker Desktop with Compose. No AWS account, cloud credentials,
Redis, or external ERP is required.

```bash
docker compose up --build
```

- Studio: <http://localhost:3002>
- Backend API and OpenAPI: <http://localhost:8001/docs>
- Readiness: <http://localhost:8001/readyz>

The first start creates the local schema and seeds `default_tenant` plus the
Production Scheduling Agent. Postgres data persists in the `pgdata` Docker
volume. This stack uses generated demo orders, machines, materials, and
maintenance data only. “Approve simulated publish” records an approval event;
it does not connect to or modify an ERP/MES system.

To stop the services without deleting local data:

```bash
docker compose down
```

To intentionally reset the local demo database:

```bash
docker compose down -v
```

## Optional hosted model

The scheduler works without an LLM. To use any hosted provider or local
inference server exposing the OpenAI-compatible chat-completions API for
natural-language intent and schedule explanations, put these values in the
ignored root `.env` file:

```dotenv
MODEL_NAME=your-model-id
MODEL_API_KEY=your-key
MODEL_API_BASE=https://api.example.com/v1
```

Set credentials on your machine; do not put real keys in manifests, source,
or chat. Compose passes only these model variables to the backend. Runs record
a clear failure if the configured explanation call fails; they do not silently
fall back after a configured provider error.

## MVP scope

Included:

- YAML agent manifest with template defaults and typed JSON-Schema workflow contracts
- Quick Build and Pro Canvas views over the same manifest-backed local agent
- design-time validation of workflow node schemas, required inputs, edge types, cycles,
  and graph reachability
- printing/scheduling semantic dependency declarations
- local sample orders, machines, materials, changeovers, and maintenance
- deterministic CP-SAT assignment with machine, material, calendar, and
  maintenance constraints
- schedule KPIs and explanation
- explicit human approval before simulated publish
- persisted run status, approvals, and append-only run events
- run history, manifest view, demo-data view, and mobile-friendly Studio

The current implementation follows the diagram's local equivalents for the agent
Studio, control, semantic/context, model, and data planes. Quick Build configures
and tests the printing template; Pro Canvas visualizes its typed workflow and
the YAML remains the portable artifact. The runtime records outcome validation
before planner approval. It does not yet offer a Git-backed authoring commit or
a general-purpose draggable graph editor.

## v0.3 local implementation sequence

1. **Foundation — implemented:** keep the manifest portable and authoritative,
   define typed workflow contracts, and reject invalid graph connections.
2. **Author and run — implemented:** start from the local printing template,
   inspect the same graph in Pro Canvas, generate a deterministic schedule, and
   require approval before simulated publishing.
3. **Validate and observe — implemented:** persist ordered run events, check hard
   schedule outcomes before approval, and run the local regression suite.
4. **Local lifecycle — next:** editable manifest round-trip, immutable version
   history and comparison, richer scenario evaluation, and configurable local
   triggers/usage estimates.
5. **Production architecture — deferred:** GitOps commits, enterprise identity,
   external connectors, sandbox/credential proxy infrastructure, environment
   promotion, A2A, and marketplace publishing.

Deferred until a pilot/customer and local foundations justify them:

- AWS/Kubernetes/Terraform and managed secret stores
- SSO/OIDC, user management, and multi-tenant administration UI
- Temporal and distributed event/message infrastructure
- ERP/MES/APS connectors, Trino, MQTT/OPC-UA, and printing protocols
- unrestricted MCP, sandbox execution, and credential proxy
- automated triggers, marketplace publishing, A2A, and skill packs
- production observability stack, FinOps, and production SLOs
- multi-stage environment promotion and model comparison playground

See [the v0.3 specification](./docs/Enterprise_Agent_Studio_v0.3_Specification.md)
for the long-term architecture, [the architecture diagram](./docs/agent_studio_v0.3_architecture.png)
for the platform planes, and [the local agent manifest](./agents/production-scheduling/manifest.yaml)
for the running MVP configuration.
