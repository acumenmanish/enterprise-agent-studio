# ADR-0003: Bring automation/workflow engine into MVP scope

## Status
Accepted (2026-09-07) — supersedes the "no connector marketplace / no
broad workflow engine" exclusion in the original MVP scope document
(Section 5, Explicitly Out of Scope).

## Context
Original MVP scope explicitly excluded a general connector marketplace and
broad workflow automation, to protect the Feb 2027 pilot date for a
5-person team. The product direction has since been revised to require
n8n-style in-platform deployment (triggers, connector nodes, one-click
activation) as part of the MVP, not just the post-pilot target state.

## Decision
Include a minimal automation engine in MVP, scoped as follows to limit
blast radius:

- Reuses the unified visual-builder core (ADR-0002) — no separate canvas.
- Reuses Temporal for durable execution — no separate workflow runtime.
- Trigger types limited to: webhook, schedule (cron), and MCP-tool-backed
  event polling. No bespoke per-SaaS trigger infrastructure in MVP.
- Connector/node library limited to the MVP's existing integration set
  (SQL, REST, CSV/Excel, MCP) rather than a broad pre-built app library —
  a general connector marketplace remains out of scope for MVP.

## Consequences
- Real, non-trivial addition to MVP scope. Team/timeline should be
  re-examined at the Sprint 2 review against actual Sprint 0/1 velocity.
- `workflow-engine/` is scaffolded now as a placeholder service boundary;
  implementation begins after the Agent Studio shell and capability
  registry exist, per the dependency order in the project plan (Section
  51) — automation cannot be built before the capability/policy layer it
  depends on.

## Open question for product/architecture review
Whether the automation engine ships in the Feb 2027 pilot or in a
fast-follow release. Flagged for the Sprint 2 architecture review.
