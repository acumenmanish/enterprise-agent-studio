# Enterprise Agent Studio — Local Scheduling MVP

Local-first prototype for the v0.3 architecture, focused on the first
production use case: a printing production-scheduling agent. The portable
agent manifest is the configuration source; the Studio uses synthetic
printing data, a deterministic OR-Tools optimizer, hard-constraint checks,
planner approval, and an append-only Postgres run-event log.

The model gateway defaults to Anthropic for natural-language intent and
schedule explanations, while retaining OpenAI-compatible endpoint support.
Without model settings, the app runs locally and generates a deterministic
explanation. A configured model does not make scheduling decisions or bypass
validation/approval. The local stack uses one `default_tenant`; it does not yet
provide user login, SSO, or production tenant administration.

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
volume; per-tenant agent manifest repositories persist in the `manifestrepo`
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

## Model provider

The optimizer runs without an LLM. For the default Anthropic model, the backend
reads the key from the ignored root `.env` file. The model name can be pinned;
otherwise the Studio uses `claude-sonnet-4-5`:

```dotenv
ANTHROPIC_API_KEY=your-key
# Optional:
MODEL_NAME=claude-sonnet-4-5
```

Existing OpenAI-compatible endpoints are still supported with `MODEL_NAME`,
`MODEL_API_KEY`, and `MODEL_API_BASE`; set `MODEL_PROVIDER` when you need to
override provider detection. Compose passes credentials only to the backend.
Keys never enter the browser or agent manifest. Runs report a provider error
instead of silently falling back when a configured model call fails.

## Run observability and LangSmith

Every scheduling run stores a local event trace in Run History, including each
LangGraph node's start, completion or failure, elapsed time, and a privacy-safe
output summary. Model request interpretation and schedule explanation are also
timed locally. A Studio run ID is included in the detail view for correlation.

LangSmith tracing is optional and disabled by default. To send LangGraph node
traces to a LangSmith project, set the following in the ignored root `.env` and
rebuild/restart the backend:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=enterprise-agent-studio
```

LangGraph traces can include workflow inputs and outputs, which may contain
planner requests, scheduling data, and approved policy constraints. Only enable
external tracing when the data is permitted to leave the local environment.
API keys used to call the model are not included in trace metadata. The UI shows
whether LangSmith was enabled for each run and its trace ID; search that ID in
the configured LangSmith project. Direct model-gateway HTTP calls are not
LangSmith spans in this MVP; their timing and failures remain visible in the
local run diagnostics.

To let a Studio user replace the default with an encrypted per-agent override,
generate and add a Fernet key to `.env`:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

```dotenv
CREDENTIAL_ENCRYPTION_KEY=paste-the-generated-key-here
```

The Studio never reads the existing `.env` key back to the browser. It displays
whether the backend key is active; a replacement is encrypted before it is
stored in the local database. Keep the encryption key backed up: losing or
rotating it without re-encrypting the override makes that saved override
unreadable.

## ERP query API connection (read-only preview)

The Quick Build Data step and Data Connections workspace can configure/test the
documented Smart Schedule AI Agent Query API and preview open orders, machines,
operations, and existing schedules. Users can enter the full HTTPS endpoint and
active bearer token in the Studio. The token is encrypted at rest and requires
`CREDENTIAL_ENCRYPTION_KEY` as described above. Alternatively configure the
endpoint and token in the ignored root `.env` file:

```dotenv
ERP_QUERY_API_URL=https://your-erp-host/ai_agent_query_api.php
ERP_API_TOKEN=your-active-bearer-token
```

The backend sends only documented `select` actions, with a 25-row preview limit,
and filters orders to `status: open`. The bearer token is never sent to the
browser or persisted in the manifest. The API documentation does not provide an
inventory or changeover alias and marks maintenance as disabled, so production
schedule generation still uses synthetic demo data until the required
capabilities and their field mappings are confirmed. Schedule approval remains
a local simulation; the preview does not write to the ERP.

## MVP scope

Included:

- YAML agent manifest with template defaults and typed JSON-Schema workflow contracts
- editable YAML import/export, design-time validation, and per-tenant local Git history
- immutable manifest versions and revision comparison
- Quick Build and Pro Canvas views over the same manifest-backed local agent
- guided domain → template → model → data → policy/context → test workflow
- editable React Flow canvas saved and versioned as the agent manifest
- LangGraph execution of the validated template graph
- editable system prompt, business rules, scenarios, and tenant-agent documents
- local lexical retrieval of relevant business-context passages for model runs
- design-time validation of workflow node schemas, required inputs, edge types, cycles,
  and graph reachability
- printing/scheduling semantic dependency declarations
- local sample orders, machines, materials, changeovers, and maintenance
- deterministic CP-SAT assignment with machine, material, calendar, and
  maintenance constraints
- schedule KPIs and explanation
- explicit human approval before simulated publish
- persisted run status, approvals, and append-only run events
- run history, manifest view, read-only ERP preview, demo-data view, and
  mobile-friendly Studio

The current implementation follows the diagram's local equivalents for the agent
Studio, control, semantic/context, model, and data planes. Quick Build and Pro
Canvas edit the same manifest. Workflow graph changes are validated and run
through LangGraph; only registered local scheduling tools have executable
handlers. Uploaded UTF-8 text/Markdown and text-based PDF policies are extracted
and stored with the local tenant-agent context; relevant passages are retrieved
for model interpretation/explanation. A model may propose supported machine
blackouts and material limits from policy text, but these remain unapplied until
the user reviews and approves the structured draft. Approved constraints are
stored with the manifest and passed through a dedicated policy node before the
optimizer. Unsupported or ambiguous policy text remains context only. Document
names and hashes, rather than full document text, are committed to the portable
manifest. Manifest saves are committed to a local, container-persisted Git
repository. The runtime records outcome validation before planner approval.

The UI supports one implemented template: Printing → Production → Scheduling.
Its ERP API connection performs a read-only preview; the optimizer still runs on
synthetic orders, machines, materials, and maintenance because the shared API
does not expose all required scheduling inputs. MCP and SQL Server connectors
are shown as future connector types, not working integrations. Raw policy text
cannot directly change deterministic hard constraints; only explicitly
reviewed, supported structured constraints are enforced. Evaluation Suite
supports independent what-if cases for objective choice, machine blackouts,
and material limits, then compares their scheduling outcomes. Publishing
remains a local simulator and requires planner approval.

## v0.3 local implementation sequence

1. **Foundation — implemented:** keep the manifest portable and authoritative,
   define typed workflow contracts, and reject invalid graph connections.
2. **Author and run — implemented:** start from the local printing template,
   inspect the same graph in Pro Canvas, generate a deterministic schedule, and
   require approval before simulated publishing.
3. **Validate and observe — implemented:** persist ordered run events, check hard
   schedule outcomes before approval, and run the local regression suite.
4. **Connect live data — first read-only milestone implemented:** test the
   documented ERP query API and inspect sanitized source previews; map the
   required inventory, maintenance, and changeover data before live scheduling.
5. **Local lifecycle — in progress:** editable manifest round-trip and local
   immutable Git history/version comparison are implemented; richer scenario
   evaluation and configurable local triggers/usage estimates remain.
6. **Production architecture — deferred:** enterprise identity,
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
