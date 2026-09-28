# Enterprise Agent Studio
## Technical Product, Architecture & Implementation Specification

**Document Type:** Product + Architecture Specification  
**Status:** Architecture Baseline — v0.3 (benchmark-aligned)  
**Version:** 0.3  
**Initial Vertical:** Printing Industry / Printing Manufacturing  
**First Killer Agent:** Production Scheduling Agent  
**Primary Customers:** ERP companies serving printing customers; individual printing companies  
**Primary Studio Operators:** Platform team and ERP implementation/AI engineering teams  
**Audience:** Product, CTO/Architecture, AI Engineering, Data Engineering, Security, DevOps/SRE, ERP/Domain SMEs

**Revision history:**
- v0.2 — architecture baseline / discussion draft
- v0.3 — benchmark alignment (OpenAI AgentKit, Copilot Studio, Claude Managed Agents): agent-as-code, two-tier authoring, typed node contracts, event-sourced run log, sandbox + credential proxy, outcome checker, triggers, version compare, usage estimator, publish approval, delegated identity, A2A, skill packs. See §72.

---

# 1. Executive Summary

## 1.1 Product Vision

We propose an **Enterprise Agent Studio**: a technical low-code environment for engineering, testing, governing, deploying and operating enterprise AI agents.

The platform is not intended to be another generic chatbot builder.

The platform should allow an AI Engineer / Solution Architect to create a governed enterprise agent with:

- domain-specific semantic context
- customer-specific semantic overlays
- governed enterprise capabilities
- MCP-based tool access
- no-mandatory-ETL data access
- controlled actions and write-back
- policy enforcement
- human-in-the-loop approvals
- multi-agent orchestration
- deterministic workflow execution
- model routing
- evaluation and regression testing
- end-to-end observability
- cost governance
- multi-tenancy
- versioning and deployment controls
- natural-language quick-start authoring with a Quick build → Pro canvas tier upgrade path
- agent-as-code: the manifest is the source of truth, GitOps-managed and exportable
- sandboxed tool execution with a credential proxy boundary
- first-class triggers (schedule, event, webhook) and outcome self-validation before human approval
- pre-deployment usage estimation with forecast-vs-actual FinOps
- A2A agent interoperability and reusable, exportable skill packs

The working product metaphor is:

> **"VS Code for Enterprise Agents"**

The first vertical implementation is **Printing Manufacturing**, with the **Production Scheduling Agent** as the first killer agent.

---

# 2. Strategic Product Positioning

## 2.1 What We Are Building

We are building an:

> **Enterprise Agentic Intelligence Platform**

with the following proposition:

> **Build governed AI agents that understand a company's business domain, use its existing enterprise capabilities without requiring universal data duplication, and take controlled actions under enterprise policies.**

For the first vertical:

> **Agentic AI Operating Layer for the Printing Factory**

## 2.2 What We Are Not Building

The platform should not attempt to win through:

- generic chat
- generic RAG
- generic no-code agents
- generic prompt management
- generic MCP support
- generic LLM routing alone
- building our own LLM
- building our own vector database
- building our own workflow engine
- replacing ERP/MES/APS as the system of record

## 2.3 Where We Intend to Differentiate

The defensible product/IP should concentrate on:

1. Printing/manufacturing domain semantic model
2. Customer-specific semantic overlays
3. Semantic-to-capability mapping
4. No-mandatory-ETL capability fabric
5. Policy-aware MCP gateway
6. Domain-specific agent templates
7. Domain-specific evaluation suites
8. Agent execution control plane
9. Controlled enterprise actions
10. Scheduling-specific optimization + AI orchestration
11. Agent-as-code artifacts with GitOps lifecycle (portable across any model provider)
12. Sandboxed execution with credential-proxy security boundary
13. Skill-pack marketplace for OEM / ERP-partner reuse

---

# 3. Business Model and Customer Operating Model

## 3.1 Customer Types

### A. ERP Companies

ERP companies serving printing businesses are a primary target.

They may:

- deploy the platform for their own customers
- configure agents on behalf of customers
- provide managed AI services
- create customer-specific semantic overlays
- build proprietary agents on top of the platform

This creates an opportunity for an **OEM / channel / implementation model**.

### B. Printing Companies

Individual printing companies can use the platform directly.

They may:

- consume deployed agents
- configure their own agents
- manage approval policies
- monitor agent performance
- integrate their own systems

## 3.2 User Personas

### Platform Product / Engineering Team

Owns:

- core platform
- printing ontology
- platform connectors
- MCP gateway
- runtime
- security
- observability
- evaluation framework

### ERP Solution Architect

Owns:

- customer architecture
- connector configuration
- customer semantic overlay
- agent deployment
- integration

### AI Engineer

Owns:

- agent graphs
- prompts/instructions
- context
- tools
- model policies
- evaluation
- debugging

### Data Engineer

Owns:

- semantic mappings
- federation
- query optimization
- data quality
- data lineage

### Printing Domain SME

Owns:

- business definitions
- KPI definitions
- constraints
- workflows
- exceptions
- scheduling rules

### Enterprise Administrator

Owns:

- users
- tenant configuration
- roles
- policies
- approvals
- audit
- deployment

### Catalog Publisher (ERP partner / tenant admin)

Owns:

- skill pack authoring and versioning
- marketplace / catalog publishing requests
- partner agent registration for A2A interop

### Planner / Production Manager

Consumes:

- schedule recommendations
- explanations
- exception alerts
- approval workflows

---

# 4. Product Architecture Principles

## Principle 1 — Business Semantics First

Agents reason over:

- business entities
- business metrics
- relationships
- capabilities

rather than raw database schemas.

## Principle 2 — No Mandatory ETL

Live/federated/API-based access should be the default.

However, materialization is allowed when required for:

- performance
- historical analysis
- ML
- high-frequency access
- source-system protection
- deterministic response time

## Principle 3 — MCP Is the Agent-Facing Capability Protocol

MCP should be used as the agent-facing interface for tools/capabilities.

It is **not** the entire connector architecture.

The platform should reuse MCP protocol/SDK components where practical and build an enterprise **MCP Gateway / Control Layer** around them.

## Principle 4 — Least Privilege

An agent receives only the tools and data it requires.

## Principle 5 — Actions Are Governed

Every write/action capability must have:

- identity
- authorization
- risk classification
- policy
- audit
- optional approval

## Principle 6 — Agents Are Versioned Software Artifacts

An agent has explicit dependencies on:

- semantic model
- tools
- policies
- model policy
- optimization engine
- prompt/instruction configuration
- evaluation suite

## Principle 7 — Runtime Behavior Must Be Reproducible

Production execution should not silently move to:

- a newer model
- a new tool
- a new semantic definition
- a new policy

without controlled upgrade.

## Principle 8 — LLMs Are Not the Deterministic System of Record

LLMs are used for:

- interpretation
- planning
- orchestration
- explanation
- exception handling

Deterministic software is used for:

- optimization
- validation
- calculations
- transactional execution
- workflow durability

## Principle 9 — Every Important Execution Is Observable

Every execution should be traceable across:

- user
- agent
- context
- model
- tool
- policy
- data
- action
- outcome
- cost

## Principle 10 — Multi-Tenant by Design

Tenant isolation is a platform-level concern, not an application convention.

---

# 5. High-Level Architecture

```text
                                    USERS
                                      │
                  ┌───────────────────┴───────────────────┐
                  │                                       │
          AGENT STUDIO                              END-USER APPS
          (Quick start · Pro canvas ·               (planner consoles,
           usage estimator · version compare ·        copilots, APIs)
           export as code)
                  │                                       │
                  └───────────────────┬───────────────────┘
                                      │
                               EXPERIENCE API
                                      │
                     ┌────────────────▼────────────────┐
                     │ AGENT CONTROL PLANE             │
                     │                                 │
                     │ Agent Registry                  │
                     │ Agent Runtime (LangGraph)       │
                     │ Orchestration (+ A2A)           │
                     │ Memory                          │
                     │ HITL                            │
                     │ Triggers (schedule/event/hook)  │
                     │ Event-Sourced Run Log *         │
                     │ Outcome Checker *               │
                     └────────────────┬────────────────┘
                                      │
                 ┌────────────────────┴─────────────────────┐
                 │                                          │
       ┌─────────▼──────────┐                    ┌──────────▼─────────┐
       │ CONTEXT /          │                    │ CAPABILITY /       │
       │ SEMANTIC PLANE     │                    │ MCP PLANE          │
       │                    │                    │                    │
       │ Domain Ontology    │                    │ MCP Gateway        │
       │ Metrics            │                    │ Tool Registry      │
       │ Glossary           │                    │ Query Gateway      │
       │ Customer Overlay   │                    │ Action Gateway     │
       │ Context Planner    │                    │ Capability Policy  │
       │ Skill Packs *      │                    │ Sandboxed Executor*│
       └─────────┬──────────┘                    │ Credential Proxy * │
                 │                               └──────────┬─────────┘
                 │                                          │
                 └────────────────────┬─────────────────────┘
                                      │
                      ┌───────────────▼────────────────┐
                      │ DATA / SYSTEM FABRIC           │
                      │                                │
                      │ Trino / APIs / SQL             │
                      │ MQTT / OPC-UA                  │
                      │ JDF / XJDF / JMF               │
                      │ Vendor APIs                    │
                      └───────────────┬────────────────┘
                                      │
           ┌──────────────────────────┼───────────────────────────┐
           │                          │                           │
          ERP                        MES                         APS
           │                          │                           │
          MIS                        CMMS                        IoT
           │                          │                           │
       Databases                   Files                      Other APIs

                   ┌────────────────────────────────┐
                   │ MODEL CONTROL PLANE            │
                   │                                │
                   │ Model Gateway (provider-       │
                   │   independent)                 │
                   │ Routing · Fallback             │
                   │ Model Policy (pinned)          │
                   │ Cost / Latency Controls        │
                   └────────────────────────────────┘


╔══════════════════════════════════════════════════════════════════════╗
║                    TRUST & CONTROL PLANE  (cross-cutting)           ║
║ IAM · Tenancy · Security · OPA Policy · Audit · Evaluation          ║
║ Observability · FinOps · Versioning · Governance · HITL             ║
║ Secrets Vault ── Credential Proxy * · Sandbox Boundary *           ║
║ GitOps / Agent-as-Code * · Catalog Publish Approval *              ║
╚══════════════════════════════════════════════════════════════════════╝

* = introduced or upgraded in v0.3
```

---

# 6. Platform Layer Model

The original six-layer model is refined into the following:

| Plane / Layer | Primary Responsibility |
|---|---|
| 1. Experience Plane | Agent Studio, applications, APIs, user interaction |
| 2. Agent Control Plane | Agent lifecycle, orchestration, execution |
| 3. Context / Semantic Plane | Domain semantics, glossary, context engineering |
| 4. Capability / MCP Plane | Tools, MCP, query/action capabilities |
| 5. Data / System Fabric | ERP, MES, APS, MIS, IoT, APIs, databases |
| 6. Model Control Plane | Model gateway, routing, fallback, model policy |
| Cross-cutting Trust & Control Plane | IAM, security, policy, audit, evaluation, observability, FinOps |

The model providers themselves are treated as an interchangeable infrastructure layer behind the Model Control Plane.

---

# 7. Enterprise Agent Studio

## 7.1 Purpose

The Agent Studio is the primary development environment for:

- AI Engineers
- Solution Architects
- Data Engineers
- Domain SMEs

It should provide technical low-code functionality while retaining advanced control.

From v0.3, the Studio operates in two authoring tiers on the **same** agent manifest:

- **Quick build** — the user describes the use case in natural language; the system proposes ranked templates with rationale and prefills all wizard slots with visible, editable defaults
- **Pro canvas** — full control over graph, semantics, tools, policies, model policy, triggers and outcomes

Both tiers read and write the same manifest (FR-021, FR-022); switching tiers never requires rework. The canvas is a view; the manifest is the source of truth.

## 7.2 Design Philosophy

The Studio should feel like:

> **An AI engineering IDE**

rather than:

> **A generic chatbot builder.**

## 7.3 Studio Workspaces

### Workspace 1 — Agent Designer

Create:

- agent identity
- objective
- responsibilities
- instructions
- graph
- sub-agents
- memory
- execution mode

### Workspace 2 — Context Designer

Configure:

- semantic model
- business glossary
- customer semantic overlay
- context policy
- context retrieval
- historical context

### Workspace 3 — Tool / MCP Studio

Manage:

- tools
- MCP servers
- tool schemas
- input/output contracts
- permissions
- risk
- versions
- source systems

### Workspace 4 — Policy Studio

Manage:

- RBAC
- ABAC
- action permissions
- data access
- approval policies
- rate limits
- tenant restrictions

### Workspace 5 — Optimization / Rules Studio

For domains such as scheduling.

Manage:

- hard constraints
- soft constraints
- objective functions
- weights
- deterministic validators
- optimization engines
- business rules

### Workspace 6 — Evaluation Studio

Manage:

- test cases
- golden datasets
- regression suites
- model comparison
- semantic tests
- tool tests
- policy tests
- action tests

### Workspace 7 — Model Playground

Compare:

- models
- latency
- quality
- tool use
- structured output
- cost
- fallback behavior

### Workspace 8 — Deployment Manager

Manage:

```text
DEV
  ↓
TEST
  ↓
STAGING
  ↓
PRODUCTION
```

### Workspace 9 — Agent Observability

Monitor:

- execution
- errors
- latency
- tools
- policy
- model
- cost
- evaluation
- actions

---

# 8. Agent Artifact Specification

An agent is a versioned software artifact.

Conceptually:

```text
Agent
│
├── Identity
├── Purpose
├── Instructions
├── Goals
├── Semantic Contract
├── Context Configuration
├── Tools / Capabilities
├── Actions
├── Policies
├── Memory
├── Model Policy
├── Execution Graph
├── Optimization Configuration
├── Evaluation Suite
├── Deployment Configuration
└── Observability Configuration
```

## 8.1 Example Agent Manifest

```yaml
agent:
  id: production-scheduling
  name: Production Scheduling Agent
  version: 1.1.0          # v0.3: new optional fields, backward-compatible
  domain: printing
  owner: platform

semantic_contract:
  printing: 1.0.0
  scheduling: 1.0.0
  capacity: 1.0.0

tools:
  - get_open_orders@2.x
  - get_machine_capacity@2.x
  - get_inventory@1.x
  - get_current_schedule@1.x
  - get_changeover_matrix@1.x
  - publish_schedule@1.x

policies:
  - scheduling-read@1.x
  - scheduling-publish@1.x

model_policy:
  id: scheduling-reasoning
  version: 1.0

optimizer:
  engine: or-tools
  version: 1.x

execution:
  default: recommend-and-approve
  on_behalf_of: planner              # optional delegated identity (FR-031)

triggers:                            # FR-027
  - type: schedule
    cron: "0 5 * * 1"                # Mondays 05:00
  - type: event
    topic: erp.order.created

outcomes:                            # FR-026
  - id: schedule-quality
    criteria:
      - feasible == true
      - late_jobs <= 2
    max_iterations: 3

sandbox_profile: tool-exec-standard # FR-025

evaluation_suite:
  id: production-scheduling-regression
  version: 1.0
```

---

# 9. Domain Semantic Architecture

## 9.1 Semantic Model Layers

### Layer A — Printing Industry Core

Target proprietary coverage: approximately **60%**.

Contains:

- entities
- relationships
- metrics
- domain terminology
- standard business concepts
- standard operational concepts
- standard scheduling concepts

### Layer B — Customer Semantic Overlay

Target customer-specific coverage: approximately **40%**.

Contains:

- renamed fields
- customer-specific entities
- customer-specific KPI definitions
- exceptions
- custom terminology
- custom relationships
- custom policies

### Layer C — Runtime Context

Contains:

- user
- tenant
- plant
- current shift
- current jobs
- machine state
- active exceptions
- current schedule
- relevant historical context

---

# 10. Printing Core Ontology

Initial ontology candidates:

```text
Commercial
├── Customer
├── Contract
├── Quote
└── Order

Job
├── PrintJob
├── JobSpecification
├── Quantity
├── Priority
└── DueDate

Material
├── Paper
├── Ink
├── Plate
└── Consumable

Production
├── ProductionRun
├── Press
├── Prepress
├── Postpress
├── Finishing
└── Packaging

Machine
├── Machine
├── Component
├── Sensor
└── Capability

Quality
├── QualityResult
├── Defect
├── Scrap
├── Rework
└── Inspection

Maintenance
├── Asset
├── Failure
├── MaintenanceEvent
└── WorkOrder

Energy
├── Meter
├── Consumption
├── Demand
└── EnergyCost

Scheduling
├── Capacity
├── Availability
├── Changeover
├── Sequence
├── Constraint
├── Schedule
└── ScheduleVersion

Business Metrics
├── OEE
├── Throughput
├── Yield
├── Waste %
├── Schedule Adherence
├── Cost / Job
├── MTBF
├── MTTR
└── Energy / Unit
```

---

# 11. Semantic Versioning & Governance

## 11.1 Rule

Existing semantic versions are immutable.

Example:

```text
Printing Core 1.4.0
```

must never be silently edited.

Create:

```text
1.4.1
1.5.0
2.0.0
```

as appropriate.

## 11.2 Version Meaning

### PATCH

Backward-compatible correction.

### MINOR

Backward-compatible addition.

### MAJOR

Breaking semantic change.

## 11.3 Semantic Contract

Every deployed agent records its semantic dependencies:

```text
Agent:
Production Scheduler 1.0

Semantic:
Printing Core 1.4
Scheduling 1.1
Capacity 1.2
```

## 11.4 Change Impact Analysis

When semantic version changes:

```text
New Semantic Version
       ↓
Dependency Analyzer
       ↓
Find affected agents
       ↓
Classify impact
       ↓
Run regression tests
       ↓
Approve / reject migration
```

Impact classification:

| Change | Impact |
|---|---|
| Add optional attribute | Low |
| Add entity | Low |
| Add metric | Medium |
| Rename entity | High |
| Rename attribute | High |
| Remove entity | Critical |
| Change KPI formula | High/Critical |
| Change relationship semantics | High |

---

# 12. Context Engineering

The platform should never indiscriminately dump source data into an LLM.

Preferred flow:

```text
User Request
    ↓
Intent Interpretation
    ↓
Semantic Interpretation
    ↓
Context Planner
    ↓
Required Entities / Metrics
    ↓
Capability Invocation
    ↓
Relevant Data
    ↓
Context Assembly
    ↓
Agent
```

## Context should include only what is needed.

Example:

```json
{
  "plant": "Plant-01",
  "planning_horizon": "2026-08-26_to_2026-09-01",
  "open_orders": 127,
  "available_presses": 8,
  "material_constraints": 6,
  "planned_maintenance": 3,
  "changeover_matrix_version": "1.4"
}
```

---

# 13. Capability Architecture

## 13.1 Business Capabilities, Not Raw Tables

Bad:

```text
run_sql()
```

Preferred:

```text
get_open_orders()
get_machine_capacity()
get_material_availability()
get_changeover_matrix()
simulate_schedule()
publish_schedule()
```

## 13.2 Tool Specification

Every tool must define:

```text
Tool ID
Name
Description
Version
Owner
Domain
Input schema
Output schema
Semantic entities
Source system
Read/Write
Risk class
Required permissions
Approval mode
Timeout
Retry policy
Audit requirement
```

---

# 14. MCP Gateway Specification

## 14.1 Decision

**Do not implement the MCP protocol from scratch.**

Reuse appropriate MCP SDK/protocol components and implement a proprietary enterprise **MCP Gateway / Control Layer**.

## 14.2 Gateway Responsibilities

- authentication
- tenant resolution
- identity propagation
- tool discovery
- tool filtering
- authorization
- policy evaluation
- schema validation
- rate limiting
- version routing
- approval routing
- audit
- tracing
- usage/cost attribution
- error normalization

## 14.3 Tool Exposure

The gateway should not expose the complete platform tool set to every agent.

Flow:

```text
Agent
 ↓
Capability Profile
 ↓
Allowed Tool Set
 ↓
Policy Filter
 ↓
Runtime Context Filter
 ↓
MCP Gateway
 ↓
Tool
```

---

# 15. Tool Governance

## 15.1 Risk Classes

### R0 — Read

Examples:

- get_orders
- get_capacity
- get_inventory

No approval.

### R1 — Analytical

Examples:

- simulate_schedule
- calculate_schedule_score
- forecast_delay

No operational side effect.

### R2 — Reversible Operational Action

Examples:

- create internal task
- create maintenance work order
- notify planner

May be autonomous under approved policy.

### R3 — Business Commitment

Examples:

- publish production schedule
- change delivery commitment
- allocate scarce material

Human approval recommended/required by policy.

### R4 — High Impact / Irreversible

Examples:

- stop machine
- cancel customer order
- financial commitment
- destructive system action

Human approval mandatory.

---

# 16. Tool Versioning

Production agents must never depend on an uncontrolled `latest` capability.

Example:

```text
get_machine_capacity@2.1
```

Version changes follow:

- PATCH = bug fix
- MINOR = backward-compatible extension
- MAJOR = breaking change

Tool upgrade process:

```text
New Tool Version
      ↓
Compatibility Check
      ↓
Affected Agent Detection
      ↓
Regression Test
      ↓
Approval
      ↓
Deployment
```

---

# 17. Preventing Unrestricted Tool Access

Use:

- least privilege
- agent capability allowlists
- role-based access
- attribute-based access
- tenant filters
- plant filters
- runtime policy evaluation
- tool risk classification

Example Production Scheduler:

```text
ALLOW
✓ get_open_orders
✓ get_machine_capacity
✓ get_inventory
✓ get_changeover_matrix
✓ get_current_schedule
✓ simulate_schedule

CONDITIONAL
△ publish_schedule

DENY
✗ stop_machine
✗ delete_job
✗ modify_machine_master
✗ change_customer
```

---

# 18. Data Architecture

## 18.1 No-Mandatory-ETL Principle

Preferred:

```text
Agent
 ↓
Semantic Layer
 ↓
Capability
 ↓
Policy
 ↓
Federation/API
 ↓
System of Record
```

But materialization is supported.

## 18.2 When Federation Is Preferred

Use federation/live access for:

- current schedules
- open orders
- machine state
- current inventory
- master data
- low/medium volume cross-system queries
- data requiring freshness

## 18.3 When Federation Is Insufficient

Materialize/cache/replicate when:

- source system is slow
- analytical load is high
- historical volume is huge
- expensive joins are frequent
- source availability is unreliable
- response time needs to be deterministic
- source ERP/MES must be protected
- ML feature generation is required

---

# 19. Hybrid Data Pattern

```text
                  SEMANTIC DATA ACCESS
                           │
             ┌─────────────┼──────────────┐
             │             │              │
          LIVE/API     FEDERATED      MATERIALIZED
             │             │              │
            ERP          Trino        Lakehouse
            MES                          │
            IoT                     Analytics / ML
```

## 19.1 System of Record

ERP/MES/APS/CMMS remain systems of record.

## 19.2 System of Intelligence

The Agent Platform becomes the system of intelligence:

- semantic abstraction
- reasoning
- recommendations
- orchestration
- optimization
- controlled actions

---

# 20. Caching Strategy

## Cache Class A — Reference Data

TTL: minutes to hours.

Examples:

- machine master
- capability master
- product metadata

## Cache Class B — Operational Snapshot

TTL: seconds to minutes.

Examples:

- machine status
- current schedule
- current inventory

## Cache Class C — Expensive Analytical Results

TTL: minutes to hours.

Examples:

- yesterday's OEE
- weekly schedule performance
- historical benchmark analysis

## Cache Class D — Tool Catalogue

Cache MCP/tool metadata separately from business data.

---

# 21. Materialization Strategy

Materialize when:

1. Source is performance-constrained
2. Query is expensive
3. Historical data is large
4. Same derived result is frequently reused
5. Deterministic response time is needed
6. Source system protection is required
7. ML features are required
8. Cross-system transformation is substantial

Materialization should be treated as a deliberate architecture choice, not a default.

---

# 22. Authorization Architecture

Recommended model:

# RBAC + ABAC + Runtime Context

## RBAC

Roles:

```text
PlatformAdmin
ERPAdmin
CatalogPublisher
AIEngineer
SolutionArchitect
Planner
ProductionManager
PlantManager
Viewer
```

## ABAC

Attributes:

```text
tenant_id
plant_id
department
machine_group
data_classification
action_risk
```

## Runtime Context

Examples:

```text
current_shift
machine_state
business_impact
schedule_status
approval_state
```

## Authorization Flow

```text
User Identity
     ↓
Role
     ↓
Tenant / Plant
     ↓
Agent Capability
     ↓
Tool Risk
     ↓
Runtime Context
     ↓
Policy Engine
     ↓
ALLOW / DENY / APPROVAL
```

---

# 23. Multi-Tenancy Architecture

Tenant is a first-class platform entity.

```text
Tenant
│
├── Users
├── Roles
├── Agents
├── Semantic Models
├── Customer Overlay
├── Tools
├── Connectors
├── Credentials
├── Policies
├── Model Policies
├── Evaluations
├── Deployments
├── Usage
├── Costs
└── Audit
```

Tenant isolation must be enforced at:

- identity
- API
- database
- semantic layer
- connector
- MCP
- model gateway
- object storage
- observability
- audit

## Deployment Modes

1. Shared SaaS
2. Dedicated tenant
3. Private cloud / customer VPC
4. On-premise

---

# 24. Human-in-the-Loop Model

Use risk-based execution.

```text
R0 Read
 → automatic

R1 Analyze/Recommend
 → automatic

R2 Reversible Action
 → policy-dependent

R3 Business Commitment
 → approval usually required

R4 High Impact / Irreversible
 → approval mandatory
```

## Production Scheduling Example

The first MVP should use:

```text
Generate
 ↓
Validate
 ↓
Score
 ↓
Recommend
 ↓
Planner Approval
 ↓
Publish
```

Avoid fully autonomous publication in MVP.

---

# 25. Model Control Plane

## 25.1 Model Independence

The agent should depend on a **Model Policy**, not a specific provider.

Example:

```text
Task: schedule explanation
 → medium reasoning model

Task: complex constraint interpretation
 → frontier reasoning model

Sensitive data
 → approved private model

Simple lookup
 → low-cost model
```

## 25.2 Model Routing Dimensions

Route using:

- task
- complexity
- sensitivity
- latency
- context size
- structured-output requirements
- tool-use quality
- reliability
- cost

---

# 26. Model Fallback

Fallback should be triggered by defined conditions.

## Hard failures

- provider unavailable
- timeout
- rate limit
- context overflow
- invalid response

## Structured execution failures

- malformed tool call
- invalid arguments
- schema failure
- structured output failure

## Validation failures

- constraint failure
- tool result inconsistency
- schedule validator failure

Fallback flow:

```text
Primary Model
      ↓
Validator
      ↓
PASS → Continue
      │
      └── FAIL
           ↓
       Retry / Fallback
           ↓
       Re-validate
```

---

# 27. Preventing Silent Model Behavior Changes

Every production agent locks:

```text
Agent version
Semantic versions
Tool versions
Policy versions
Model Policy version
Optimizer version
Prompt/instruction version
Evaluation suite version
```

Any change creates a new deployable version.

No production agent should automatically use an untested model.

---

# 28. Production Scheduling Agent — Reference Architecture

This is the most important reference implementation.

```text
                         PLANNER
                           │
                           ▼
                 PRODUCTION SCHEDULER
                       ORCHESTRATOR
                           │
             ┌─────────────┼─────────────┐
             │             │             │
          Orders        Capacity      Materials
          Service        Service       Service
             │             │             │
             └─────────────┼─────────────┘
                           │
                     Context Planner
                           │
                     Semantic Layer
                           │
                     MCP Gateway
                           │
            ┌──────────────┼───────────────┐
            │              │               │
           ERP            MES             APS
            │              │               │
            └──────────────┼───────────────┘
                           │
                 Deterministic Optimizer
                           │
                Candidate Schedule(s)
                           │
                    Constraint Validator
                           │
                    Business KPI Scoring
                           │
                    Schedule Explanation
                           │
                    Human Approval
                           │
                    Publish Schedule
                           │
                      ERP / MES / APS
```

---

# 29. Scheduling Agent Responsibilities

## 29.1 It Should

- understand scheduling requests
- identify planning horizon
- identify orders in scope
- retrieve production capacity
- retrieve material availability
- retrieve machine availability
- retrieve changeover constraints
- retrieve planned maintenance
- identify scheduling constraints
- configure optimization objectives
- invoke deterministic optimizer
- evaluate candidate schedules
- compare alternatives
- explain tradeoffs
- recommend a schedule
- request approval
- publish approved schedule

## 29.2 It Should Not

- invent production capacity
- override hard constraints
- bypass policy
- directly modify ERP/MES without authorization
- optimize solely through LLM reasoning
- silently change business priority rules

---

# 30. LLM + Optimization Architecture

The LLM should not be the mathematical scheduler.

Preferred:

```text
User Request
   ↓
LLM
   ↓
Interpret objective / constraints
   ↓
Structured Scheduling Problem
   ↓
Optimization Engine
   ↓
Candidate Schedules
   ↓
Validator
   ↓
Scoring
   ↓
LLM
   ↓
Explain / Recommend
```

Potential optimization technology:

- OR-Tools
- customer APS engine
- commercial optimization solver where required
- custom deterministic scheduling engine for domain-specific rules

---

# 31. Scheduling Agent Execution Example

User:

> "Create next week's production schedule, prioritizing urgent customer orders while minimizing changeover time."

## Step 1 — Interpret

```text
Planning horizon = next week
Priority = urgent customer orders
Primary optimization objective = minimize changeover
Secondary objective = schedule adherence
```

## Step 2 — Retrieve

```text
Open orders
Machine capacity
Machine calendars
Material availability
Planned maintenance
Changeover matrix
Current schedule
Customer priority
```

## Step 3 — Build Optimization Problem

```text
Hard Constraints
- machine capability
- material availability
- machine downtime
- production capacity
- required process sequence

Soft Constraints
- minimize changeover
- minimize lateness
- prioritize premium customers
- balance machine utilization
```

## Step 4 — Generate Candidates

Example:

```text
Candidate A
Late jobs: 2
Changeovers: 14
Utilization: 88%

Candidate B
Late jobs: 1
Changeovers: 18
Utilization: 91%

Candidate C
Late jobs: 3
Changeovers: 11
Utilization: 84%
```

## Step 5 — Recommend

> Candidate B provides the best SLA outcome while maintaining acceptable changeover cost.

## Step 6 — Approval

Planner approves.

## Step 7 — Publication

Schedule is written to the approved enterprise scheduling system.

---

# 32. Scheduling Studio — Agent Graph

```text
START
  │
  ▼
Understand Scheduling Request
  │
  ▼
Determine Planning Horizon
  │
  ▼
Fetch Orders
  │
  ▼
Fetch Capacity
  │
  ▼
Fetch Materials
  │
  ▼
Fetch Maintenance
  │
  ▼
Fetch Changeover Rules
  │
  ▼
Build Optimization Problem
  │
  ▼
Generate Candidate Schedules
  │
  ▼
Validate Hard Constraints
  │
  ├── FAIL → Repair / Re-run
  │
  ▼
Score Candidates
  │
  ▼
Explain Tradeoffs
  │
  ▼
Recommend Best Candidate
  │
  ▼
Human Approval
  │
  ├── REJECT → revise
  │
  ▼
Publish Schedule
  │
  ▼
END
```

---

# 33. Multi-Agent Architecture

The platform should support a central orchestrator with specialized workers.

However, not every worker needs to be an LLM agent.

Example:

```text
                    Scheduler Orchestrator
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
   Orders Service      Capacity Service     Material Service
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                       Optimization Engine
                              │
                       Validator Service
                              │
                        Explanation Agent
```

Use an LLM agent where reasoning/orchestration is valuable.

Use deterministic services where deterministic behavior is better.

---

# 34. LangGraph vs Temporal

## LangGraph

Use for:

- agent state
- LLM orchestration
- conditional reasoning
- tool selection
- multi-agent graph
- human interaction state

## Temporal

Use for:

- durable long-running workflow
- retries
- waiting
- scheduling
- timers
- recovery
- exactly-once/business workflow semantics where applicable
- enterprise process durability

Recommended separation:

```text
LangGraph
= intelligent decision/orchestration layer

Temporal
= durable workflow execution layer
```

Do not make the LLM responsible for durable workflow guarantees.

### v0.3 addition — event-sourced run log (FR-024, NFR-010)

The append-only run event log is the durability source of truth: every execution records intent, context selections, tool calls, optimizer invocations, validations, approvals and outcomes as events. LangGraph state and Temporal workflows are executors of that log. Every run must be:

- **resumable** — re-enter from the last persisted event after crash, eviction or timeout
- **replayable** — reconstruct any historical run for debugging, audit and evaluation without re-executing side effects
- **wakeable** — trigger-fired or long-running runs suspended on external events resume without state loss

---

# 35. Agent Evaluation Framework

Evaluation must test the entire system.

## 35.1 Evaluation Dimensions

### Semantic

Did the agent understand the request?

### Planning

Did it select the right execution path?

### Tool

Did it select the correct capabilities?

### Data

Did it retrieve correct data?

### Optimization

Was the generated schedule feasible and effective?

### Decision

Was the recommendation appropriate?

### Policy

Did it respect authorization?

### Action

Did it perform the correct write-back?

### Operations

What were latency and cost?

---

# 36. Scheduling Evaluation Dataset

Initial target:

**500–2,000 representative scenarios**.

Each scenario should contain:

```text
Orders
Machine capacities
Machine calendars
Materials
Changeovers
Maintenance constraints
Priorities
Due dates
Historical context
Expected constraints
Expected outcome characteristics
```

Evaluation metrics:

```text
Feasibility %
Late Jobs
Changeover Count
Capacity Utilization
Priority Satisfaction
Schedule Adherence
Cost
Latency
```

---

# 37. Regression Testing

Every change to:

- model
- prompt/instructions
- tool
- semantic model
- optimization engine
- policy

must trigger relevant regression testing.

Example:

```text
Before
Feasible = 99.3%
Late Jobs = 4.1
Changeovers = 16.8

After
Feasible = 98.1%
Late Jobs = 5.2
Changeovers = 17.3

Result:
REGRESSION
Deployment blocked
```

---

# 38. Agent Debugger

The Agent Studio should provide structured execution debugging.

```text
USER REQUEST
      ↓
INTENT
      ↓
SEMANTIC INTERPRETATION
      ↓
CONTEXT SELECTION
      ↓
TOOL SELECTION
      ↓
TOOL ARGUMENTS
      ↓
DATA RESULT
      ↓
OPTIMIZER
      ↓
VALIDATION
      ↓
MODEL RESPONSE
      ↓
FINAL ACTION
```

## Failure Categories

```text
SEMANTIC_ERROR
DATA_ERROR
TOOL_ERROR
POLICY_ERROR
PLANNING_ERROR
MODEL_ERROR
OPTIMIZATION_ERROR
INTEGRATION_ERROR
```

The goal is to identify the root cause without exposing private model chain-of-thought.

---

# 39. Agent Execution Contract

Every production execution should have a structured contract:

```text
WHO
WHAT
WHY
WITH WHICH CONTEXT
USING WHICH TOOLS
USING WHICH MODEL
UNDER WHICH POLICY
AGAINST WHICH SEMANTIC VERSION
WHAT DATA WAS ACCESSED
WHAT DECISION WAS PRODUCED
WHAT ACTION WAS TAKEN
WHAT WAS THE RESULT
WHAT DID IT COST
```

Required execution identifiers:

```text
tenant_id
user_id
agent_id
agent_version
run_id
trace_id
semantic_model_version
policy_version
model_id
model_policy_version
prompt_version
tool_versions
optimizer_version
data_sources
latency
token_usage
cost
approval
action
result
trigger_id
on_behalf_of_user_id
outcome_result
```

---

# 40. Observability Architecture

```text
                 OpenTelemetry
                      │
          ┌───────────┼───────────┐
          │           │           │
        Metrics      Logs       Traces
          │           │           │
      Prometheus     Loki       Tempo
          │           │           │
          └───────────┴───────────┘
                      │
                    Grafana

LLM / Agent-specific tracing
          ↓
      Langfuse
```

## Trace Example

```text
User
 ↓
Agent
 ↓
Planner
 ↓
Model
 ↓
Tool Selection
 ↓
MCP
 ↓
Policy
 ↓
Query
 ↓
ERP/MES/APS
 ↓
Optimizer
 ↓
Validator
 ↓
Approval
 ↓
Publish
```

---

# 41. Observability Retention

Use tiered retention.

## Hot

7–30 days:

- detailed traces
- full debugging information
- tool execution

## Warm

30–180 days:

- summarized traces
- performance
- errors
- model metrics

## Cold

1–7 years where required:

- audit
- policy decisions
- approvals
- transactional history
- security records

Full sensitive LLM payloads should have shorter/default retention unless explicitly required.

---

# 42. Trace Sampling

Suggested baseline:

```text
Successful low-risk runs:
10–25% full trace

Failed runs:
100%

Policy violations:
100%

Human approvals:
100%

Business transactions:
100%

Schedule publication:
100%
```

Sampling should be configurable per tenant.

---

# 43. FinOps

Every execution should be economically attributable.

```text
Tenant
  ↓
Agent
  ↓
Run
  ↓
Model
  ↓
Tokens
  ↓
Tool calls
  ↓
Optimization compute
  ↓
Data/query compute
  ↓
Infrastructure allocation
  ↓
TOTAL COST
```

Example:

```text
Tenant: ABC Printing
Agent: Production Scheduler

LLM:                ₹1.20
Optimization:       ₹0.35
Data/query:         ₹0.12
Infrastructure:     ₹0.18
---------------------------
Total:              ₹1.85
```

---

# 44. FinOps Controls

Support:

- per-tenant budgets
- per-agent budgets
- per-user budgets
- per-run cost limits
- model cost ceilings
- daily/monthly alerts
- cost anomaly detection
- model optimization recommendations

---

# 45. Agent Health Dashboard

Example:

```text
Production Scheduling Agent

Runs Today:                1,247
Successful:                  98.7%
Failed:                       1.3%
Policy Violations:              0
Human Approvals:              143
Avg Latency:                 2.7 sec
Avg Cost/Run:               ₹0.84
Evaluation Score:             94.2%
Schedule Feasibility:          99.1%
```

Failure categories:

```text
Semantic ambiguity          18
Tool timeout                  9
Data unavailable              6
Policy denial                 4
Model failure                 2
Optimizer failure             1
```

---

# 46. Security Architecture

Required capabilities:

- SSO
- OAuth/OIDC
- MFA where required
- RBAC
- ABAC
- tenant isolation
- secrets management
- encryption in transit
- encryption at rest
- audit logging
- tool authorization
- data classification
- action approval
- network isolation
- private deployment option

---

# 47. Secret Management

Connector credentials should never be stored as agent configuration.

Use:

- cloud secret manager
- Vault
- KMS-backed encryption

The agent should receive a capability reference, not raw credentials.

### v0.3 upgrade — architectural boundary (FR-025, NFR-011, ADR-014)

Credentials never enter the sandbox. Tools executing untrusted or model-generated input (SQL, code, composed HTTP calls) run in an isolated sandbox with no credential access and no direct egress. Authenticated calls pass through a **credential proxy** that fetches the secret from the vault at call time, performs the call, and returns only the result — prompt injection inside a tool therefore cannot reach raw tokens. Per-tool egress allowlists are enforced at the proxy, not inside the sandbox.

---

# 48. API / Connector Architecture

Connectors should be **semantic capability adapters**.

A connector should expose capabilities such as:

```text
query_orders()
query_jobs()
query_machine_status()
query_capacity()
query_inventory()
create_schedule()
publish_schedule()
```

instead of exposing a large list of raw vendor endpoints.

---

# 49. Printing Integration Strategy

Initial protocols:

- JDF
- XJDF
- JMF
- PrintTalk where required
- OPC-UA
- MQTT
- REST APIs
- vendor-specific APIs
- MIS APIs
- MES APIs
- APS APIs

The platform should normalize them into enterprise capabilities.

---

# 50. Initial Connector Priorities

Priority 1:

1. ERP order management
2. Production/MES
3. Scheduling/APS
4. Machine/IoT
5. Inventory/material
6. Maintenance/CMMS
7. Printing MIS

Priority should ultimately be determined by the target ERP partner and pilot customer.

---

# 51. Recommended Technical Stack

| Capability | Initial recommendation |
|---|---|
| Frontend | React / Next.js |
| UI | Tailwind + shadcn/ui |
| Agent canvas | React Flow |
| Backend | Python / FastAPI |
| Agent runtime | LangGraph |
| Durable workflows | Temporal |
| Model gateway | LiteLLM initially |
| Query federation | Trino |
| Database | PostgreSQL |
| Vector store | pgvector initially |
| Cache | Redis |
| Event bus | Kafka / Redpanda |
| Industrial telemetry | MQTT |
| Industrial protocol | OPC-UA |
| Printing | JDF / XJDF / JMF |
| MCP | MCP SDK + custom enterprise gateway |
| Sandboxed execution | gVisor / Firecracker-class isolation |
| Credential proxy | Custom, vault-backed, egress-allowlisted |
| GitOps | Manifest repos + ArgoCD / Flux |
| A2A interop | A2A protocol SDK |
| Policy | OPA |
| IAM | Keycloak initially; enterprise IdP integrations later |
| Secrets | Vault / cloud secret manager |
| Object storage | S3-compatible |
| Containers | Kubernetes |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Metrics | Prometheus |
| Logs | Loki |
| Traces | Tempo |
| Instrumentation | OpenTelemetry |
| LLM observability | Langfuse |
| Evaluation | Custom evaluation service + Langfuse |
| Scheduling optimizer | OR-Tools initially; pluggable optimizer interface |

---

# 52. Technology Selection Rubric

For each critical component, score 1–5.

| Criterion | Weight |
|---|---:|
| Enterprise maturity | 15% |
| Scalability | 15% |
| Security | 15% |
| Extensibility | 10% |
| Ecosystem | 10% |
| Performance | 10% |
| Multi-tenancy | 10% |
| Operational complexity | 5% |
| Cost | 5% |
| Vendor independence | 5% |

Weighted score:

```text
Σ(score × weight)
```

Critical component target:

> **≥ 4.0 / 5.0**

Also document:

- build vs buy
- lock-in risk
- migration path
- operational burden
- license model
- support model

---

# 53. What to Build vs Reuse

## Reuse

Do not build from scratch:

- LLMs
- vector databases
- distributed tracing protocol
- workflow engine
- Kubernetes
- generic databases
- generic model providers
- MCP protocol implementation

## Build

Proprietary platform IP:

1. Printing semantic model
2. Customer semantic overlay framework
3. Semantic registry
4. Semantic dependency/version engine
5. Semantic-to-capability mapper
6. MCP enterprise gateway/control plane
7. Capability registry
8. Policy-aware tool execution
9. Agent Studio
10. Agent execution control plane
11. Domain evaluation framework
12. Scheduling optimization orchestration
13. Printing agent templates
14. Customer deployment/OEM layer

---

# 54. Functional Requirements

## FR-001 Agent Creation

The system shall allow authorized users to create an agent from:

- blank template
- domain template
- existing agent version

## FR-002 Agent Versioning

The system shall assign immutable agent versions.

## FR-003 Agent Graph

The system shall support visual construction of execution graphs.

## FR-004 Sub-Agent / Worker Delegation

The system shall support a central orchestrator delegating work to specialized agents/services.

## FR-005 Semantic Selection

The system shall allow an agent to declare its semantic dependencies.

## FR-006 Customer Overlay

The system shall allow customer-specific semantic extensions without modifying the base printing model.

## FR-007 Tool Registry

The system shall maintain versioned capabilities.

## FR-008 Tool Policy

The system shall prevent unauthorized tool access.

## FR-009 MCP Gateway

The system shall expose governed capabilities through MCP.

## FR-010 Query Federation

The system shall support live/federated access to supported enterprise systems.

## FR-011 Materialization

The system shall support controlled derived/materialized datasets.

## FR-012 Human Approval

The system shall support configurable approval workflows.

## FR-013 Model Routing

The system shall select models through model policies.

## FR-014 Model Fallback

The system shall support controlled fallback and retry.

## FR-015 Evaluation

The system shall execute domain regression suites before production deployment.

## FR-016 Deployment

The system shall support DEV → TEST → STAGING → PRODUCTION.

## FR-017 Execution Trace

The system shall retain structured execution metadata.

## FR-018 Cost Attribution

The system shall attribute cost to tenant, agent and run.

## FR-019 Multi-Tenancy

The system shall provide tenant isolation.

## FR-020 Audit

The system shall audit significant reads, writes, approvals and policy decisions.

## FR-021 Agent-as-Code Manifest Round-Trip

The system shall treat the agent manifest (spec §8) as the **single source of truth** for every agent.

The system shall:

- render any manifest as an editable canvas graph and any canvas graph as an equivalent manifest, losslessly, in both directions
- store manifests in a version-controlled repository per tenant (GitOps model); canvas saves produce commits, not opaque state
- support manifest import/export as portable YAML, independent of any vendor SDK or provider
- support manifest-level CI: linting, schema validation, policy checks and evaluation suite execution triggered on commit

*Rationale: OpenAI's sunsetting of Agent Builder (Nov 30, 2026) demonstrates that closed, builder-locked artifacts strand users. The artifact must outlive any single UI or vendor.*

## FR-022 Two-Tier Authoring Modes

The system shall provide two authoring tiers operating on the same underlying manifest:

- **Quick build** — natural-language description of the use case; the system proposes ranked templates (with rationale) and prefills all wizard slots with visible, editable defaults
- **Pro canvas** — full control over graph, tools, semantics, policies, model policy

The system shall guarantee that an agent started in Quick build can be opened in Pro canvas, and vice versa, without loss or rework.

## FR-023 Typed Node Contracts

Every node in an execution graph shall declare a typed input/output contract (JSON Schema).

The system shall validate edges at design time and at deployment time, and reject connections whose types are incompatible. Tool schemas (spec §13.2) remain the inner contract of tool nodes; node contracts are the outer contract between graph nodes.

## FR-024 Event-Sourced Run Log

Every agent execution shall be recorded as an **append-only event log** (run events: intent, context selections, tool calls, optimizer invocations, validations, approvals, outcomes).

The system shall support:

- **resume**: re-enter a run from the last persisted event after process crash, pod eviction or timeout
- **replay**: reconstruct any historical run for debugging, audit and evaluation without re-executing side effects
- **wake**: trigger-based and long-running runs suspended awaiting external events shall be resumable without loss of state

The run log is the durability mechanism; LangGraph state and Temporal workflows are its executors, not its source of truth.

## FR-025 Sandboxed Tool Execution and Credential Proxy

Tools that execute untrusted or model-generated input — SQL execution, code execution, HTTP requests with model-composed parameters — shall run inside an isolated sandbox (process/container isolation, no direct network egress, no filesystem persistence unless declared).

Credentials shall **never** be mounted inside the sandbox. All authenticated calls shall pass through a credential proxy:

- the proxy holds a vault reference, fetches the secret from the secrets vault at call time, performs the authenticated call, and returns only the result
- prompt injection or tool-output manipulation inside the sandbox therefore cannot reach raw credentials
- per-tool egress allowlists are enforced at the proxy, not inside the sandbox

This requirement upgrades spec §47 from a storage rule to an architectural boundary.

## FR-026 Outcome Checker

The system shall support an optional **outcome-checker node** declaring success criteria (schema validation, threshold metrics, rubric-based self-evaluation).

Before presenting a result for human approval, the agent shall self-evaluate its output against the criteria and iterate up to a configurable bound. Failed outcomes after the bound shall escalate to the human with the failure evidence attached — never silently downgraded.

## FR-027 First-Class Triggers

Agents shall be invocable through first-class triggers:

- **schedule** (cron/recurring)
- **event** (message-bus topics, e.g. new order published, machine state changed)
- **webhook** (external systems)

Triggers are versioned with the agent: changing a trigger definition creates a new agent version. Trigger firings are recorded in the run log and are subject to the same policies, budgets and approvals as user-invoked runs.

## FR-028 Version Compare and Transcript Harvesting

The Evaluation Studio shall support:

- side-by-side comparison of two agent versions on the same scenario set, with per-metric deltas and regression flags
- harvest of production run transcripts (from the event-sourced log, with PII redaction policy) into new evaluation scenarios
- evaluation execution via API for CI/CD integration

## FR-029 Pre-Deployment Usage Estimator

Before deployment, the system shall produce a forecast per agent:

- model cost per 1k runs (from template benchmark runs and the selected model policy)
- latency distribution against the agent's SLO class
- infrastructure cost estimate (optimization compute, query compute, sandbox time)

The forecast shall be stored with the deployment record and compared against actuals post-deployment (FinOps feedback loop, extends spec §43–§44).

## FR-030 Catalog Publish Approval

Publishing an agent version to a tenant catalog, ERP-partner marketplace, or customer-facing surface shall require an explicit approval by a tenant administrator or delegated publisher role.

Publishing an agent to production shall additionally require the evaluation threshold gate (spec §37, §56). Catalog approval and evaluation approval are separate, sequential gates.

## FR-031 Delegated Per-User Identity

The system shall support agents acting **on behalf of a specific user** using per-user delegated tokens (OAuth 2.0/OIDC flow), stored in the vault and fetched at call time through the credential proxy.

Tool authorizations shall be evaluated against both the agent's capability policy and the delegated user's permissions. Audit records shall capture both the agent identity and the on-behalf-of user identity.

## FR-032 Agent-to-Agent (A2A) Interoperability

The orchestrator shall expose an A2A-compatible endpoint allowing external agents (e.g. ERP partners' agents) to delegate tasks to platform agents, and platform orchestrators to delegate tasks to registered external agents.

External agents register through the same governance path as tools: capability declaration, risk classification, policy binding, version pinning.

## FR-033 Skill Packs

The template marketplace shall support **skill packs**: versioned, exportable bundles of instructions, few-shot scenarios, prompt fragments and tool references, composable into agents and templates.

Skill packs follow the same immutability and version-pinning rules as all other agent dependencies (spec §11, §16, §27).

---

---

# 55. Non-Functional Requirements

## NFR-001 Security

Security must be designed into every execution layer.

## NFR-002 Tenant Isolation

No tenant may access another tenant's data, configuration or execution state.

## NFR-003 Reproducibility

A production run must be reproducible from recorded versions and configuration where source data permits.

## NFR-004 Observability

All production actions and failures must be traceable.

## NFR-005 Availability

Initial production target should be defined per deployment profile.

## NFR-006 Latency

Interactive agent operations should have explicit SLOs.

For example:

- simple query: target < 3 seconds
- complex analysis: target < 10 seconds
- scheduling optimization: asynchronous when necessary

## NFR-007 Scalability

Services should scale independently:

- agent runtime
- MCP gateway
- query layer
- evaluation
- model gateway

## NFR-008 Extensibility

Connectors and tools must be pluggable.

## NFR-009 Vendor Independence

LLM provider migration must not require agent redesign.

## NFR-010 Execution Durability

No single process failure shall lose more than the in-flight event of an agent run. All runs shall be resumable from the event-sourced log (FR-024).

## NFR-011 Credential Isolation

No credential material shall be readable from agent runtime memory, tool sandboxes, logs, traces or manifests — only vault references and proxy-mediated call results (FR-025, FR-031).

---

---

# 56. Environment Model

```text
Development
    ↓
Automated Validation
    ↓
Test
    ↓
Evaluation Suite
    ↓
Staging
    ↓
Security / Regression
    ↓
Production
```

Promotion requires:

- tests passed
- policy checks
- dependency compatibility
- evaluation threshold
- approval where required

---

# 57. Deployment Options

## SaaS

Shared platform with tenant isolation.

## Dedicated

Dedicated runtime for customer/ERP tenant.

## Private Cloud

Customer VPC/VNet.

## On-Premise

For customers requiring local operation.

The architecture should preserve a common deployment model across all four.

---

# 58. Roadmap

## Phase 0 — Architecture / Technical Prototype

Target: 6–8 weeks.

Build:

- tenant model
- initial Agent Studio shell
- basic agent runtime
- initial semantic registry
- MCP gateway prototype
- one printing connector
- model gateway
- basic OTel
- scheduling proof of concept
- first evaluation cases

## Phase 1 — Production Scheduling MVP

Target: 4–6 months.

Build:

- multi-tenancy
- Agent Studio
- printing semantic model v1
- customer overlay
- Trino
- ERP/MES/APS connectors
- MCP gateway
- OPA policy
- scheduling optimizer
- HITL
- evaluation
- observability
- FinOps
- versioning
- deployment pipeline
- sandboxed tool executor + credential proxy
- event-sourced run log (resume / replay / wake)
- triggers (schedule / event / webhook)
- outcome checker
- pre-deploy usage estimator
- catalog publish approval gate

First agent:

> **Production Scheduling Agent**

## Phase 2 — Production Intelligence Expansion

Add:

- Production Intelligence Agent
- Maintenance Agent
- Quality Agent
- Energy Agent
- Cost Agent
- Executive Agent

## Phase 3 — Enterprise Platform

Add:

- advanced SSO
- private deployment
- HA/DR
- OEM capabilities
- customer marketplace
- billing
- advanced governance
- model evaluation at scale

---

# 59. Initial Development Team

Indicative team:

```text
1 Product / Domain Lead
1 Principal Architect
2 AI / Agent Engineers
2 Backend Engineers
2 Data / Semantic Engineers
2 Frontend Engineers
1 DevOps / SRE
1 QA / Automation
1 UX / Product Designer
```

Approximate:

**12 people**

Plus part-time:

- printing SME
- ERP SME
- security architect
- cloud architect

---

# 60. Indicative Development Cost

## Prototype

**₹20–35 lakh**

## Printing Scheduling MVP

**₹80 lakh–₹1.5 crore**

## Enterprise-ready v1

**₹2–4 crore**

## Heavily hardened enterprise platform

Potentially **₹4–7 crore**

Actual cost will depend on:

- seniority
- engineering location
- percentage of buy vs build
- enterprise security scope
- connector complexity
- private deployment requirements

---

# 61. Indicative Infrastructure Cost

## Development

Approximately:

**₹1–3 lakh/month**

## Pilot

Approximately:

**₹3–8 lakh/month**

## Early SaaS Production

Approximately:

**₹8–20 lakh/month**

LLM provider costs should be tracked separately.

---

# 62. First Production Scheduling Agent — MVP Scope

The first version should deliberately be constrained.

## Inputs

- open orders
- due dates
- priority
- machine capabilities
- machine availability
- capacity
- material availability
- planned maintenance
- changeover matrix
- production calendar

## Constraints

### Hard

- machine capability
- machine availability
- material availability
- process sequence
- maintenance windows
- capacity

### Soft

- priority
- due date
- changeover
- utilization
- customer importance

## Outputs

- candidate schedules
- selected schedule
- KPI comparison
- constraint violations
- trade-off explanation
- jobs at risk
- capacity bottlenecks

## Action

Initially:

> **Recommend + Human Approval + Publish**

Not autonomous publishing.

---

# 63. Production Scheduling Agent KPIs

The agent itself should be evaluated using scheduling KPIs.

### Schedule quality

- feasibility
- on-time delivery
- late jobs
- total tardiness
- changeover count
- changeover duration
- machine utilization
- capacity utilization
- priority satisfaction

### Agent quality

- semantic accuracy
- tool selection accuracy
- constraint interpretation
- explanation quality
- policy compliance
- action accuracy

### Technical

- latency
- model cost
- optimization runtime
- failure rate

---

# 64. Reference Studio Interaction

The engineer should experience the following workflow:

```text
1. Create Agent
      ↓
2. Select Printing / Scheduling Template
      ↓
3. Define Objective
      ↓
4. Select Semantic Models
      ↓
5. Define Customer Overlay
      ↓
6. Select Tools / MCP Capabilities
      ↓
7. Configure Scheduling Constraints
      ↓
8. Configure Optimization Engine
      ↓
9. Configure Policies
      ↓
10. Configure Model Policy
      ↓
11. Build / Review Agent Graph
      ↓
12. Run Test Cases
      ↓
13. Compare Models
      ↓
14. Run Regression Suite
      ↓
15. Deploy to Staging
      ↓
16. Validate
      ↓
17. Promote to Production
      ↓
18. Observe
      ↓
19. Improve / Version
```

---

# 65. Product Lifecycle

```text
DISCOVER
   ↓
DESIGN
   ↓
CONFIGURE
   ↓
TEST
   ↓
EVALUATE
   ↓
DEPLOY
   ↓
OPERATE
   ↓
OBSERVE
   ↓
IMPROVE
   ↓
VERSION
   ↓
REDEPLOY
```

The Agent Studio should support the entire lifecycle.

---

# 66. Open Architecture Decisions

These should remain open until validated with pilot customers:

1. Exact printing ontology boundary
2. First ERP/MIS vendor integration
3. First APS/scheduling integration
4. Trino vs Dremio/Denodo/Starburst for enterprise deployments
5. OR-Tools vs commercial optimization engine
6. Shared vs dedicated runtime policy
7. Final IAM choice
8. Final LLM observability vendor
9. Data retention policy per customer
10. Deployment sizing/SLOs

---

# 67. Architecture Decision Records

## ADR-001 — Printing as MVP

**Decision:** Printing industry is the first vertical.

**Reason:** It aligns with the intended domain expertise and provides a specific semantic/business capability layer rather than a generic horizontal agent platform.

**Status:** 

---

## ADR-002 — Production Scheduling as First Killer Agent

**Decision:** The Production Scheduling Agent is the first production-grade agent.

**Reason:** It exercises the platform's hardest capabilities:

- semantic interpretation
- cross-system data retrieval
- constraints
- optimization
- multi-step orchestration
- tool governance
- human approval
- transactional write-back
- evaluation

**Status:** 

---

## ADR-003 — Agent Runtime

**Decision:** Use LangGraph.

**Reason:** Good fit for graph-based agent orchestration and stateful agent execution.

**Status:** Accepted.

---

## ADR-004 — Durable Workflow

**Decision:** Use Temporal for durable workflow execution.

**Reason:** LLM agent logic should not be responsible for durable enterprise workflow semantics.

**Status:** Accepted.

---

## ADR-005 — Model Gateway

**Decision:** Use a reusable model gateway foundation initially and expose our own Model Control Plane.

**Initial candidate:** LiteLLM.

**Reason:** Avoid rebuilding generic provider routing while preserving model independence.

**Status:** Proposed.

---

## ADR-006 — MCP

**Decision:** Reuse MCP protocol/SDK components and build an enterprise MCP Gateway / Control Layer.

**Reason:** MCP is useful as the agent-facing capability protocol, but enterprise governance requires:

- policy
- tenant isolation
- tool filtering
- audit
- versioning
- approval
- observability

**Status:** Accepted as architectural direction.

---

## ADR-007 — Semantic Versioning

**Decision:** Semantic models are immutable versioned contracts.

**Reason:** Prevent silent behavior changes in production agents.

**Status:** Accepted.

---

## ADR-008 — No Mandatory ETL

**Decision:** No mandatory data duplication; federation/live access is preferred where practical.

**Reason:** Freshness, reduced integration duplication and lower data movement.

**Status:** Accepted.

---

## ADR-009 — Hybrid Data

**Decision:** Permit caching and materialization for performance, historical analytics, ML, reliability and source protection.

**Status:** Accepted.

---

## ADR-010 — Authorization

**Decision:** RBAC + ABAC + runtime policy/context.

**Status:** Accepted.

---

## ADR-011 — Human Approval

**Decision:** Risk-based approval.

**MVP policy:** Publishing production schedules requires human approval.

**Status:** Accepted.

---

## ADR-012 — LLM + Deterministic Optimization

**Decision:** Use LLM for intent, orchestration and explanation; deterministic optimizer for schedule generation and constraint solving.

**Status:** Accepted.

## ADR-013 — Agent-as-Code

**Decision:** The manifest YAML is the source of truth for every agent; the canvas is a view. All agents are GitOps-managed, version-controlled, exportable artifacts.

**Reason:** OpenAI's deprecation of Agent Builder (Nov 30, 2026) in favor of SDK code and NL-authored Workspace Agents shows that closed builder artifacts are a dead end. Portability of the artifact is a first-class product requirement, not a migration feature.

**Status:** Accepted.

## ADR-014 — Sandbox and Credential Boundary

**Decision:** Untrusted/model-generated tool execution runs in isolated sandboxes with no credential access; all authenticated egress passes through a credential proxy backed by the vault.

**Reason:** The platform exposes SQL, API and MCP tools whose arguments are partially model-composed. Without this boundary, prompt injection is a direct path into customer ERP/MES systems. This mirrors the managed-agent principle of decoupling the "brain" from the "hands."

**Status:** Accepted.

## ADR-015 — Vendor Independence as Deliberate Architecture

**Decision:** Agents bind model policies, never providers. Provider changes are configuration changes under regression testing, not redesigns.

**Reason:** Both observed extremes are traps: closed builders get sunset (OpenAI Agent Builder), and managed agent platforms lock execution to one vendor's models and infrastructure (Claude Managed Agents: Claude models, Anthropic infra, session pricing). The platform's enterprise customers and OEM partners require the agent artifact to survive either fate.

**Status:** Accepted.

---

# P.5 Impact on Existing Sections (v0.2)

| Section | Impact |
|---|---|
| §7.1 Studio purpose | Add two-tier authoring (FR-022); canvas becomes a manifest view (FR-021) |
| §8 Agent manifest | Add fields: `triggers[]`, `outcomes[]`, `sandbox_profile`, `quick_build_defaults` |
| §13–§17 Capability architecture | Add sandbox executor and credential proxy to capability plane (FR-025) |
| §24 HITL | Outcome checker precedes approval (FR-026) |
| §34 LangGraph vs Temporal | Clarify: run log is source of truth; executors implement resume/wake (FR-024, NFR-010) |
| §35–§37 Evaluation | Add version compare, transcript harvesting, CI API (FR-028) |
| §39 Execution contract | Add `trigger_id`, `on_behalf_of_user_id`, `outcome_result` fields |
| §43–§44 FinOps | Add pre-deploy estimator and forecast-vs-actual loop (FR-029) |
| §47 Secret management | Upgraded from storage rule to architectural boundary (FR-025, NFR-011, ADR-014) |
| §58 Roadmap | Phase 1 adds: sandbox executor, credential proxy, event-sourced run log, triggers, outcome checker, estimator, publish gate; Phase 3 adds A2A and skill-pack marketplace |
| §70 Review checklist | Add: run-log durability, sandbox boundary, publish gate, per-user identity, estimator confirmed |

---

# 68. Recommended Next Design Artifact

The next engineering artifact should be:

# **Production Scheduling Agent — Detailed Solution Design**

It should specify:

1. User journeys
2. Agent Studio screens
3. Agent graph
4. Semantic model
5. Customer overlay
6. Tool catalogue
7. MCP interface
8. Data contracts
9. ERP/MES/APS integration
10. Scheduling optimization model
11. Policy rules
12. Approval workflow
13. Evaluation dataset structure
14. Execution trace schema
15. API contracts
16. Database schemas
17. Deployment architecture
18. Production SLOs
19. Test strategy
20. Failure/recovery scenarios

---

# 69. Final Product Definition

The platform is:

> **An enterprise engineering and operating environment for governed AI agents.**

A production agent is not merely:

```text
Prompt + LLM
```

It is:

```text
Agent
+
Semantic Contract
+
Context
+
Capabilities
+
Tools
+
Policies
+
Model Policy
+
Optimization / Rules
+
Memory
+
Evaluation
+
Observability
+
Versioning
+
Deployment
```

The first reference implementation is:

> **Printing Manufacturing → Production Scheduling Agent**

The long-term platform then expands naturally into:

```text
Production
Maintenance
Quality
Energy
Cost
Scheduling
Executive Intelligence
```

while the underlying platform remains reusable.

---

# 70. Architecture Review Checklist

Before implementation, confirm that the team agrees on:

- [ ] Printing is the MVP vertical
- [ ] Production Scheduling is the first killer agent
- [ ] ERP companies are a primary customer/channel
- [ ] Agent Studio is technical low-code
- [ ] LangGraph is the agent runtime
- [ ] Temporal is the durable workflow engine
- [ ] MCP is the agent-facing protocol
- [ ] Enterprise MCP Gateway is required
- [ ] Semantic model is a first-class platform component
- [ ] Semantic versions are immutable
- [ ] Customer overlays are separate from the base model
- [ ] No mandatory ETL is the default
- [ ] Federation + cache + materialization form a hybrid data strategy
- [ ] RBAC + ABAC + contextual policy is the authorization model
- [ ] Tool access follows least privilege
- [ ] Tool versions are explicit
- [ ] Production schedule publication requires human approval in MVP
- [ ] LLM does not replace deterministic scheduling optimization
- [ ] Model policy abstracts providers
- [ ] Model changes require regression testing
- [ ] Every production execution is traceable
- [ ] Cost is attributable to tenant/agent/run
- [ ] Agent debugging is structured and evidence-based
- [ ] System of record remains ERP/MES/APS
- [ ] Agent platform is the system of intelligence
- [ ] SaaS + dedicated + private deployment is part of the long-term architecture
- [ ] Agent manifest is the source of truth; canvas ⇄ code round-trip via GitOps
- [ ] Quick build and Pro canvas operate on the same manifest
- [ ] Untrusted tool execution is sandboxed; credentials reachable only via proxy
- [ ] Every run is event-sourced: resume, replay, wake
- [ ] Outcome checker precedes human approval
- [ ] Triggers are versioned with the agent
- [ ] Catalog publishing requires admin approval
- [ ] Delegated per-user (OAuth) identity is supported
- [ ] A2A interop and skill packs are planned

---

# 71. North Star

The long-term North Star is:

> **An ERP-independent Agentic Intelligence layer for the printing industry that understands printing business semantics, connects existing enterprise systems through governed capabilities, orchestrates specialized agents and deterministic business services, and enables safe, measurable and auditable operational decisions.**

For the first MVP, success is not "we built an agent."

Success is:

> **A Production Scheduling Agent can understand a planner's intent, retrieve the correct live enterprise context, construct and validate a feasible schedule using deterministic optimization, explain trade-offs, respect enterprise policies, obtain required approval, publish the approved schedule, and provide a complete execution/audit trail.**

That single use case will validate almost every critical capability of the Enterprise Agent Studio.

---

# 72. v0.3 Revision Notes — Benchmark Alignment

v0.3 aligns the platform with the observed trajectories of OpenAI AgentKit (Agent Builder + Evals sunset Nov 30, 2026, direction moving to SDK code and natural-language Workspace Agents), Microsoft Copilot Studio (two-tier authoring, ALM, DLP connector governance, admin publish approval, skills, A2A GA, version-compare evaluation, usage estimator), and Anthropic Claude Managed Agents (durable event-sourced sessions with crash recovery, sandbox/credential boundary, outcome self-evaluation, built-in OAuth — with the caution that it is Claude-models-only on Anthropic infrastructure).

Two principles are preserved as deliberate differentiators: **vendor-independent agent artifacts** (agents bind model policies, never providers — ADR-015) and the **semantic plane + deterministic optimization boundary**, which none of the three benchmark platforms offers.

### Impact on existing v0.2 sections

| Section | Impact |
|---|---|
| §7.1 Studio purpose | Add two-tier authoring (FR-022); canvas becomes a manifest view (FR-021) |
| §8 Agent manifest | Add fields: `triggers[]`, `outcomes[]`, `sandbox_profile`, `quick_build_defaults` |
| §13–§17 Capability architecture | Add sandbox executor and credential proxy to capability plane (FR-025) |
| §24 HITL | Outcome checker precedes approval (FR-026) |
| §34 LangGraph vs Temporal | Clarify: run log is source of truth; executors implement resume/wake (FR-024, NFR-010) |
| §35–§37 Evaluation | Add version compare, transcript harvesting, CI API (FR-028) |
| §39 Execution contract | Add `trigger_id`, `on_behalf_of_user_id`, `outcome_result` fields |
| §43–§44 FinOps | Add pre-deploy estimator and forecast-vs-actual loop (FR-029) |
| §47 Secret management | Upgraded from storage rule to architectural boundary (FR-025, NFR-011, ADR-014) |
| §58 Roadmap | Phase 1 adds: sandbox executor, credential proxy, event-sourced run log, triggers, outcome checker, estimator, publish gate; Phase 3 adds A2A and skill-pack marketplace |
| §70 Review checklist | Add: run-log durability, sandbox boundary, publish gate, per-user identity, estimator confirmed |

---

### Full requirement delta

The complete v0.3 patch (FR-021 → FR-033, NFR-010 → NFR-011, ADR-013 → ADR-015 with rationale) is integrated inline into this document; the standalone patch file remains available as the review delta.
