# ADR-0002: One visual-builder core, two compile targets

## Status
Accepted (2026-09-07)

## Context
The platform must support two authoring experiences: governed agent
building (originally scoped) and n8n-style automation/workflow deployment
(added to MVP scope on 2026-09-07). Building these as two separate visual
tools would roughly double canvas, node-registry, and governance-integration
effort across a 5-person team.

## Decision
Build a single proprietary canvas on React Flow with one shared node/edge
schema, capability registry, policy layer, and versioning model. The canvas
has two modes:

- **Agent mode**: compiles the graph to a LangGraph state machine, executed
  as a Temporal workflow. Used for the Production Scheduling Agent and
  future agent templates.
- **Automation mode**: compiles the graph to a trigger → action workflow
  (webhook / cron / event trigger, then a sequence of capability calls),
  also executed as a Temporal workflow. Used for the n8n-style deployment
  capability.

Both modes consume the same MCP-backed capability/tool registry, the same
OPA-backed policy layer, the same semantic model, and the same run
debugger. Only the compiler target and the node palette differ per mode.

We explicitly reject forking/embedding an existing OSS visual builder
(e.g. LangFlow): its node model is coupled to LangChain concepts, not to
our capability/policy/semantic governance layer, and retrofitting
governance onto someone else's node system is historically harder than it
looks.

## Consequences
- Higher upfront canvas/compiler investment than forking an existing tool.
- Governance (policy, semantic mapping, versioning, audit) is native to
  every node in both modes, not bolted on.
- Node schema becomes a first-class contract (see `templates/` and
  `agents/production-scheduling/` for the first consumers) — changes to it
  are architecturally significant and require a new ADR.

## Follow-up
Revisit at the Sprint 2 architecture review once canvas + compiler
estimates exist, to confirm timeline impact against the Feb 2027 pilot
date.
