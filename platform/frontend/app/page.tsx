"use client";

import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Empty,
  Input,
  InputNumber,
  Layout,
  List,
  Menu,
  Row,
  Space,
  Spin,
  Statistic,
  Steps,
  Tabs,
  Table,
  Tag,
  Typography,
  Select,
  message,
} from "antd";
import {
  AppstoreOutlined,
  BuildOutlined,
  CodeOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  HistoryOutlined,
  ReloadOutlined,
  ScheduleOutlined,
  ShareAltOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useState } from "react";

const { Content, Header, Sider } = Layout;
const { Paragraph, Text, Title } = Typography;
const API = "/api/backend/api/v1/studio";

type ScheduleEntry = {
  order_id: string;
  customer: string;
  product: string;
  quantity: number;
  machine_id: string;
  machine_name: string;
  day: number;
  start_hour: number;
  duration_hours: number;
  due_day: number;
  late_by_days: number;
  priority: number;
  material: string;
};

type ScheduleResult = {
  status: string;
  solver_status: string;
  objective_value: number;
  planning_horizon_days: number;
  metrics: {
    orders_scheduled: number;
    late_jobs: number;
    total_changeover_hours: number;
    machine_utilization_percent: number;
  };
  schedule: ScheduleEntry[];
  validation: { passed: boolean; checks: string[]; violations: string[] };
  approval_required: boolean;
  publish_status: string;
  explanation: string;
  model: string;
};

type RunSummary = {
  id: string;
  agent_id: string;
  status: string;
  created_at: string | null;
  result: ScheduleResult | null;
};

type RunDetail = RunSummary & {
  request: { objective: string; planning_horizon_days: number };
  events: { sequence: number; type: string; payload: Record<string, unknown> }[];
  approval: {
    id: string;
    status: string;
    decision_by: string | null;
    comment: string | null;
  } | null;
};

type Manifest = {
  manifest_yaml: string;
  manifest: {
    agent: {
      id: string;
      name: string;
      version: string;
      domain: string;
      objective: string;
      instructions: string;
    };
    semantic_contract: Record<string, string>;
    tools: string[];
    policies: string[];
    optimizer: { engine: string; version: string; objective_weights: Record<string, number> };
    execution: { default: string; tenant_id: string };
    triggers: unknown[];
    outcomes: { id: string; criteria: string[]; max_iterations: number }[];
    sandbox_profile: string;
    quick_build_defaults: {
      planning_horizon_days: number;
      objective: "balanced" | "due_date" | "changeover";
      template_id: string;
    };
    execution_graph: {
      nodes: {
        id: string;
        type: string;
        inputs: { properties: Record<string, { type: string }> };
        outputs: { properties: Record<string, { type: string }> };
      }[];
      edges: { from: string; to: string }[];
    };
  };
  model_configured: boolean;
};

type DemoData = {
  orders: {
    id: string;
    customer: string;
    product: string;
    quantity: number;
    due_day: number;
    priority: number;
    required_material: string;
    required_capability: string;
  }[];
  machines: {
    id: string;
    name: string;
    capabilities: string[];
    hours_per_day: number;
    available_days: number[];
    speed_units_per_hour: number;
  }[];
  materials: { id: string; available_quantity: number }[];
  horizon_days: number;
};

type ModelStatus = { configured: boolean; model: string | null; mode: string };
type Workspace =
  | "builder"
  | "designer"
  | "runs"
  | "evaluations"
  | "manifest"
  | "data";

const navigation = [
  { key: "builder", label: "Agent Designer", icon: <BuildOutlined /> },
  { key: "designer", label: "Schedule Studio", icon: <ScheduleOutlined /> },
  { key: "runs", label: "Run History", icon: <HistoryOutlined /> },
  { key: "evaluations", label: "Evaluation Suite", icon: <ExperimentOutlined /> },
  { key: "manifest", label: "Agent as Code", icon: <CodeOutlined /> },
  { key: "data", label: "Demo Data", icon: <DatabaseOutlined /> },
];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body: unknown = await response.json();
  if (!response.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? String(body.detail)
        : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return body as T;
}

export default function AgentStudio() {
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace>("builder");
  const [authoringMode, setAuthoringMode] = useState<"quick-build" | "pro-canvas">(
    "quick-build",
  );
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [demoData, setDemoData] = useState<DemoData | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [evaluationResult, setEvaluationResult] = useState<{
    suite: string;
    cases_run: number;
    passed: number;
    results: {
      case_id: string;
      name: string;
      status: string;
      score: number;
      metrics: ScheduleResult["metrics"];
      solver_status: string;
    }[];
  } | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [planningDays, setPlanningDays] = useState(5);
  const [objective, setObjective] = useState(
    "balanced",
  );
  const [requestText, setRequestText] = useState("");
  const [initialLoading, setInitialLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messageApi, contextHolder] = message.useMessage();

  const refreshRuns = useCallback(async () => {
    setRuns(await api<RunSummary[]>("/runs"));
  }, []);

  const loadInitial = useCallback(async () => {
    setInitialLoading(true);
    setError(null);
    try {
      const [manifestResponse, modelResponse, dataResponse, runResponse] =
        await Promise.all([
          api<Manifest>("/manifest"),
          api<ModelStatus>("/model/status"),
          api<DemoData>("/demo-data"),
          api<RunSummary[]>("/runs"),
        ]);
      setManifest(manifestResponse);
      setModelStatus(modelResponse);
      setDemoData(dataResponse);
      setRuns(runResponse);
      setPlanningDays(manifestResponse.manifest.quick_build_defaults.planning_horizon_days);
      setObjective(manifestResponse.manifest.quick_build_defaults.objective);
      if (runResponse[0]) {
        setSelectedRun(await api<RunDetail>(`/runs/${runResponse[0].id}`));
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load Studio data");
    } finally {
      setInitialLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  const openRun = async (runId: string) => {
    setError(null);
    try {
      setSelectedRun(await api<RunDetail>(`/runs/${runId}`));
      setActiveWorkspace("runs");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load run details");
    }
  };

  const createSchedule = async () => {
    setRunning(true);
    setError(null);
    try {
      const response = await api<{ run_id: string }>("/schedule/run", {
        method: "POST",
        body: JSON.stringify({
          planning_horizon_days: planningDays,
          objective,
          request_text: requestText || null,
        }),
      });
      await refreshRuns();
      setSelectedRun(await api<RunDetail>(`/runs/${response.run_id}`));
      setActiveWorkspace("designer");
      messageApi.success("Schedule generated; planner approval is required to publish.");
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Schedule run failed";
      setError(detail);
      messageApi.error(detail);
    } finally {
      setRunning(false);
    }
  };

  const decideApproval = async (decision: "approve" | "reject") => {
    if (!selectedRun) return;
    setError(null);
    try {
      await api(`/runs/${selectedRun.id}/approval`, {
        method: "POST",
        body: JSON.stringify({ decision }),
      });
      setSelectedRun(await api<RunDetail>(`/runs/${selectedRun.id}`));
      await refreshRuns();
      messageApi.success(
        decision === "approve"
          ? "Approved schedule recorded in the local publish simulator."
          : "Schedule rejected.",
      );
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Approval failed";
      setError(detail);
      messageApi.error(detail);
    }
  };

  const runEvaluations = async () => {
    setEvaluating(true);
    setError(null);
    try {
      setEvaluationResult(
        await api("/evaluations/run", { method: "POST", body: JSON.stringify({}) }),
      );
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Evaluation suite failed";
      setError(detail);
      messageApi.error(detail);
    } finally {
      setEvaluating(false);
    }
  };

  const scheduleColumns: ColumnsType<ScheduleEntry> = [
    { title: "Job", dataIndex: "order_id", key: "order_id", fixed: "left" },
    { title: "Customer", dataIndex: "customer", key: "customer" },
    { title: "Product", dataIndex: "product", key: "product" },
    {
      title: "Quantity",
      dataIndex: "quantity",
      key: "quantity",
      render: (quantity: number) => quantity.toLocaleString(),
    },
    { title: "Machine", dataIndex: "machine_name", key: "machine_name" },
    {
      title: "Day",
      dataIndex: "day",
      key: "day",
      render: (day: number) => `Day ${day + 1}`,
    },
    {
      title: "Start",
      dataIndex: "start_hour",
      key: "start_hour",
      render: (hour: number) => `${String(8 + hour).padStart(2, "0")}:00`,
    },
    {
      title: "Hours",
      dataIndex: "duration_hours",
      key: "duration_hours",
      render: (hours: number) => `${hours} h`,
    },
    {
      title: "Due",
      dataIndex: "due_day",
      key: "due_day",
      render: (day: number) => `Day ${day}`,
    },
    {
      title: "Schedule",
      key: "lateness",
      render: (_, entry) =>
        entry.late_by_days > 0 ? (
          <Tag color="red">{entry.late_by_days}d late</Tag>
        ) : (
          <Tag color="green">On time</Tag>
        ),
    },
  ];

  const renderSchedule = (run: RunDetail | null) => {
    if (!run?.result) {
      return (
        <Empty
          description="Generate a schedule to see a candidate plan and its constraint results."
        />
      );
    }
    const result = run.result;
    return (
      <Space direction="vertical" size="large" style={{ display: "flex" }}>
        <Row gutter={[12, 12]}>
          <Col xs={12} md={6}>
            <Card><Statistic title="Jobs scheduled" value={result.metrics.orders_scheduled} /></Card>
          </Col>
          <Col xs={12} md={6}>
            <Card><Statistic title="Late jobs" value={result.metrics.late_jobs} /></Card>
          </Col>
          <Col xs={12} md={6}>
            <Card><Statistic title="Changeover estimate" value={result.metrics.total_changeover_hours} suffix="h" /></Card>
          </Col>
          <Col xs={12} md={6}>
            <Card><Statistic title="Machine utilization" value={result.metrics.machine_utilization_percent} suffix="%" /></Card>
          </Col>
        </Row>
        <Card
          title="Candidate production schedule"
          extra={
            <Tag color={run.status === "published" ? "green" : run.status === "awaiting_approval" ? "gold" : "default"}>
              {run.status.replaceAll("_", " ")}
            </Tag>
          }
        >
          <Alert
            type={result.validation.passed ? "success" : "error"}
            showIcon
            message={
              result.validation.passed
                ? "Hard-constraint validation passed"
                : "Hard-constraint validation failed"
            }
            description={
              result.validation.violations.length
                ? result.validation.violations.join("; ")
                : result.validation.checks.join(" · ")
            }
            style={{ marginBottom: 16 }}
          />
          <Table
            rowKey="order_id"
            columns={scheduleColumns}
            dataSource={result.schedule}
            pagination={false}
            scroll={{ x: 850 }}
            size="small"
          />
        </Card>
        <Card title="Schedule explanation">
          <Paragraph>{result.explanation}</Paragraph>
          <Text type="secondary">
            Solver: {result.solver_status} · Model: {result.model} · Optimizer objective: {result.objective_value}
          </Text>
        </Card>
        {run.status === "awaiting_approval" && (
          <Card title="Planner approval required" type="inner">
            <Paragraph>
              Publishing is simulated locally. No ERP/MES system is connected or changed.
            </Paragraph>
            <Space wrap>
              <Button type="primary" onClick={() => void decideApproval("approve")}>
                Approve simulated publish
              </Button>
              <Button danger onClick={() => void decideApproval("reject")}>
                Reject schedule
              </Button>
            </Space>
          </Card>
        )}
        <Card title="Run event log">
          <List
            dataSource={run.events}
            renderItem={(event) => (
              <List.Item>
                <Space direction="vertical" size={0}>
                  <Text strong>{event.sequence}. {event.type}</Text>
                  <Text type="secondary" code>{JSON.stringify(event.payload)}</Text>
                </Space>
              </List.Item>
            )}
          />
        </Card>
      </Space>
    );
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {contextHolder}
      <Sider theme="light" collapsible breakpoint="md" collapsedWidth={0}>
        <div style={{ padding: "18px 16px", fontWeight: 700, fontSize: 17 }}>
          <AppstoreOutlined /> Agent Studio
        </div>
        <Menu
          mode="inline"
          selectedKeys={[activeWorkspace]}
          onClick={({ key }) => setActiveWorkspace(key as Workspace)}
          items={navigation}
        />
      </Sider>
      <Layout style={{ minWidth: 0 }}>
        <Header
          style={{
            background: "#fff",
            padding: "0 20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
          }}
        >
          <Title level={4} ellipsis style={{ margin: 0, minWidth: 0 }}>
            {navigation.find(({ key }) => key === activeWorkspace)?.label}
          </Title>
          <Space>
            {modelStatus && (
              <Tag color={modelStatus.configured ? "blue" : "default"}>
                {modelStatus.configured ? modelStatus.model : "Local deterministic mode"}
              </Tag>
            )}
            <Button
              aria-label="Refresh"
              icon={<ReloadOutlined />}
              onClick={() => void loadInitial()}
            />
          </Space>
        </Header>
        <Content style={{ margin: 20, minWidth: 0 }}>
          {error && (
            <Alert
              type="error"
              showIcon
              closable
              message="Studio request failed"
              description={error}
              onClose={() => setError(null)}
              style={{ marginBottom: 16 }}
            />
          )}
          {initialLoading ? (
            <Card><Spin tip="Loading local Agent Studio..." /></Card>
          ) : !manifest || !demoData ? (
            <Card>
              <Empty description="Studio data is unavailable">
                <Button type="primary" onClick={() => void loadInitial()}>Retry</Button>
              </Empty>
            </Card>
          ) : activeWorkspace === "designer" ? (
            <Space direction="vertical" size="large" style={{ display: "flex" }}>
              <Card>
                <Row gutter={[24, 20]} align="middle">
                  <Col xs={24} lg={15}>
                    <Text type="secondary">{manifest.manifest.agent.domain.toUpperCase()} · VERSION {manifest.manifest.agent.version}</Text>
                    <Title level={2} style={{ marginTop: 8 }}>{manifest.manifest.agent.name}</Title>
                    <Paragraph>{manifest.manifest.agent.objective}</Paragraph>
                    <Space wrap>
                      <Tag color="blue">{manifest.manifest.optimizer.engine}</Tag>
                      <Tag>{manifest.manifest.tools.length} governed capabilities</Tag>
                      <Tag color="gold">Publish requires approval</Tag>
                    </Space>
                  </Col>
                  <Col xs={24} lg={9}>
                    <Card type="inner" title="Build a schedule">
                      <Space direction="vertical" style={{ display: "flex" }}>
                        <Text>Planning horizon (days)</Text>
                        <InputNumber min={1} max={demoData.horizon_days} value={planningDays} onChange={(value) => setPlanningDays(value ?? 1)} style={{ width: "100%" }} />
                        <Text>Scheduling objective</Text>
                        <Select
                          value={objective}
                          onChange={setObjective}
                          options={[
                            { value: "balanced", label: "Balance all objectives" },
                            { value: "due_date", label: "Prioritize due dates" },
                            { value: "changeover", label: "Minimize changeovers" },
                          ]}
                        />
                        <Text>Optional natural-language request</Text>
                        <Input.TextArea
                          rows={2}
                          value={requestText}
                          onChange={(event) => setRequestText(event.target.value)}
                          maxLength={1000}
                          placeholder={modelStatus?.configured ? "Describe the schedule you need" : "Configure a model to use natural-language scheduling"}
                          disabled={!modelStatus?.configured}
                        />
                        <Button type="primary" icon={<ScheduleOutlined />} loading={running} onClick={() => void createSchedule()}>
                          Generate & validate schedule
                        </Button>
                      </Space>
                    </Card>
                  </Col>
                </Row>
              </Card>
              {selectedRun ? (
                renderSchedule(selectedRun)
              ) : (
                <Card title="MVP workflow">
                  <Descriptions column={{ xs: 1, sm: 2, lg: 4 }}>
                    <Descriptions.Item label="1. Inputs">{demoData.orders.length} orders · {demoData.machines.length} machines</Descriptions.Item>
                    <Descriptions.Item label="2. Optimizer">OR-Tools CP-SAT</Descriptions.Item>
                    <Descriptions.Item label="3. Validation">Hard capacity, material and maintenance constraints</Descriptions.Item>
                    <Descriptions.Item label="4. Action">Human-approved local publish simulation</Descriptions.Item>
                  </Descriptions>
                </Card>
              )}
            </Space>
          ) : activeWorkspace === "builder" ? (
            <Space direction="vertical" size="large" style={{ display: "flex" }}>
              <Card>
                <Row gutter={[24, 20]} align="middle">
                  <Col xs={24} lg={16}>
                    <Text type="secondary">
                      {manifest.manifest.agent.domain.toUpperCase()} · AGENT-AS-CODE · v
                      {manifest.manifest.agent.version}
                    </Text>
                    <Title level={2} style={{ marginTop: 8 }}>
                      Design a governed production agent
                    </Title>
                    <Paragraph>
                      Start from the printing scheduling template, then inspect the same
                      manifest as a typed execution graph. The local runtime stays
                      deterministic and requires planner approval before simulated publish.
                    </Paragraph>
                  </Col>
                  <Col xs={24} lg={8}>
                    <Space wrap>
                      <Tag color="blue">Local template</Tag>
                      <Tag color="green">Manifest-backed</Tag>
                      <Tag color="gold">Approval gated</Tag>
                    </Space>
                  </Col>
                </Row>
              </Card>
              <Tabs
                activeKey={authoringMode}
                onChange={(key) =>
                  setAuthoringMode(key as "quick-build" | "pro-canvas")
                }
                items={[
                  {
                    key: "quick-build",
                    label: "Quick Build",
                    children: (
                      <Row gutter={[16, 16]}>
                        <Col xs={24} xl={14}>
                          <Card title="1 · Choose a local template">
                            <Card type="inner" title={manifest.manifest.agent.name}>
                              <Paragraph>
                                {manifest.manifest.agent.objective}
                              </Paragraph>
                              <Space wrap>
                                <Tag color="blue">{manifest.manifest.agent.domain}</Tag>
                                <Tag>{manifest.manifest.optimizer.engine}</Tag>
                                <Tag>{manifest.manifest.tools.length} capabilities</Tag>
                              </Space>
                            </Card>
                            <Divider />
                            <Row gutter={[16, 16]}>
                              <Col xs={24} sm={12}>
                                <Text strong>Planning horizon</Text>
                                <InputNumber
                                  min={1}
                                  max={demoData.horizon_days}
                                  value={planningDays}
                                  onChange={(value) => setPlanningDays(value ?? 1)}
                                  style={{ width: "100%", marginTop: 8 }}
                                />
                              </Col>
                              <Col xs={24} sm={12}>
                                <Text strong>Scheduling objective</Text>
                                <Select
                                  value={objective}
                                  onChange={setObjective}
                                  style={{ width: "100%", marginTop: 8 }}
                                  options={[
                                    { value: "balanced", label: "Balance all objectives" },
                                    { value: "due_date", label: "Prioritize due dates" },
                                    { value: "changeover", label: "Minimize changeovers" },
                                  ]}
                                />
                              </Col>
                            </Row>
                            <Paragraph type="secondary" style={{ marginTop: 16 }}>
                              Template defaults are editable and come from the agent
                              manifest. Free-form intent is available in Schedule Studio
                              only when a model endpoint is configured.
                            </Paragraph>
                            <Button
                              type="primary"
                              icon={<ScheduleOutlined />}
                              loading={running}
                              onClick={() => void createSchedule()}
                            >
                              Build and validate a schedule
                            </Button>
                          </Card>
                        </Col>
                        <Col xs={24} xl={10}>
                          <Card title="2 · Review the configured workflow">
                            <Steps
                              direction="vertical"
                              size="small"
                              current={-1}
                              items={manifest.manifest.execution_graph.nodes.map((node) => ({
                                title: node.id.replaceAll("_", " "),
                                description: node.type,
                              }))}
                            />
                          </Card>
                          <Card title="3 · Local runtime boundary" style={{ marginTop: 16 }}>
                            <Descriptions column={1} size="small">
                              <Descriptions.Item label="Data">
                                {demoData.orders.length} synthetic orders
                              </Descriptions.Item>
                              <Descriptions.Item label="Optimizer">
                                OR-Tools CP-SAT
                              </Descriptions.Item>
                              <Descriptions.Item label="Action">
                                Local simulator, explicit approval
                              </Descriptions.Item>
                            </Descriptions>
                          </Card>
                        </Col>
                      </Row>
                    ),
                  },
                  {
                    key: "pro-canvas",
                    label: "Pro Canvas",
                    children: (
                      <Space direction="vertical" size="large" style={{ display: "flex" }}>
                        <Card
                          title="Typed execution graph"
                          extra={<Tag color="green">Manifest contract validated on load</Tag>}
                        >
                          <Row gutter={[12, 12]}>
                            {manifest.manifest.execution_graph.nodes.map((node, index) => (
                              <Col xs={24} md={12} xl={8} key={node.id}>
                                <Card
                                  size="small"
                                  title={`${index + 1}. ${node.id.replaceAll("_", " ")}`}
                                  extra={<Tag>{node.type}</Tag>}
                                >
                                  <Text strong>Inputs</Text>
                                  <Paragraph code>
                                    {Object.entries(node.inputs.properties)
                                      .map(([name, schema]) => `${name}: ${schema.type}`)
                                      .join(", ") || "No required input"}
                                  </Paragraph>
                                  <Text strong>Outputs</Text>
                                  <Paragraph code>
                                    {Object.entries(node.outputs.properties)
                                      .map(([name, schema]) => `${name}: ${schema.type}`)
                                      .join(", ") || "No output"}
                                  </Paragraph>
                                </Card>
                              </Col>
                            ))}
                          </Row>
                          <Divider />
                          <List
                            size="small"
                            header={<Text strong>Validated node connections</Text>}
                            dataSource={manifest.manifest.execution_graph.edges}
                            renderItem={(edge) => (
                              <List.Item>
                                <Space>
                                  <Tag>{edge.from}</Tag>
                                  <ShareAltOutlined />
                                  <Tag>{edge.to}</Tag>
                                </Space>
                              </List.Item>
                            )}
                          />
                        </Card>
                        <Card
                          title="Manifest-backed agent configuration"
                          extra={<Button onClick={() => setActiveWorkspace("manifest")}>View YAML</Button>}
                        >
                          <Descriptions column={{ xs: 1, md: 2 }}>
                            <Descriptions.Item label="Semantics">
                              {Object.keys(manifest.manifest.semantic_contract).join(", ")}
                            </Descriptions.Item>
                            <Descriptions.Item label="Policies">
                              {manifest.manifest.policies.join(", ")}
                            </Descriptions.Item>
                            <Descriptions.Item label="Outcome gate">
                              {manifest.manifest.outcomes
                                .flatMap((outcome) => outcome.criteria)
                                .join(", ")}
                            </Descriptions.Item>
                            <Descriptions.Item label="Sandbox profile">
                              {manifest.manifest.sandbox_profile}
                            </Descriptions.Item>
                          </Descriptions>
                        </Card>
                      </Space>
                    ),
                  },
                ]}
              />
            </Space>
          ) : activeWorkspace === "runs" ? (
            <Row gutter={[16, 16]}>
              <Col xs={24} xl={8}>
                <Card title="Recent scheduling runs">
                  {runs.length === 0 ? (
                    <Empty description="No runs yet" />
                  ) : (
                    <List
                      dataSource={runs}
                      renderItem={(run) => (
                        <List.Item
                          onClick={() => void openRun(run.id)}
                          style={{ cursor: "pointer" }}
                        >
                          <Space direction="vertical" size={2}>
                            <Text strong>{run.status.replaceAll("_", " ")}</Text>
                            <Text type="secondary">{run.created_at ? new Date(run.created_at).toLocaleString() : run.id}</Text>
                            <Text code>{run.id.slice(0, 8)}</Text>
                          </Space>
                        </List.Item>
                      )}
                    />
                  )}
                </Card>
              </Col>
              <Col xs={24} xl={16}>
                {selectedRun ? renderSchedule(selectedRun) : <Card><Empty description="Select a run to inspect its schedule, decision, and event log." /></Card>}
              </Col>
            </Row>
          ) : activeWorkspace === "evaluations" ? (
            <Space direction="vertical" size="large" style={{ display: "flex" }}>
              <Card
                title="Printing scheduling regression suite"
                extra={<Tag color="blue">3 deterministic scenarios</Tag>}
              >
                <Paragraph>
                  Runs the same local orders through balanced, due-date, and changeover objectives. Each schedule is checked against the optimizer’s machine, material, availability, and maintenance constraints.
                </Paragraph>
                <Button type="primary" loading={evaluating} onClick={() => void runEvaluations()}>
                  Run evaluation suite
                </Button>
              </Card>
              {evaluationResult && (
                <Card title={`Results: ${evaluationResult.passed}/${evaluationResult.cases_run} passed`}>
                  <Table
                    rowKey="case_id"
                    pagination={false}
                    dataSource={evaluationResult.results}
                    columns={[
                      { title: "Scenario", dataIndex: "name", key: "name" },
                      { title: "Result", dataIndex: "status", key: "status", render: (status: string) => <Tag color={status === "passed" ? "green" : "red"}>{status}</Tag> },
                      { title: "Score", dataIndex: "score", key: "score", render: (score: number) => `${score}%` },
                      { title: "Scheduled jobs", key: "scheduled", render: (_, row) => row.metrics.orders_scheduled },
                      { title: "Late jobs", key: "late", render: (_, row) => row.metrics.late_jobs },
                      { title: "Changeover", key: "changeover", render: (_, row) => `${row.metrics.total_changeover_hours} h` },
                      { title: "Solver", dataIndex: "solver_status", key: "solver_status" },
                    ]}
                  />
                </Card>
              )}
            </Space>
          ) : activeWorkspace === "manifest" ? (
            <Space direction="vertical" size="large" style={{ display: "flex" }}>
              <Card title="Portable agent manifest" extra={<Tag color="green">Source of truth</Tag>}>
                <Paragraph>
                  This versioned YAML manifest pins the printing semantic contract, tools, policies, optimizer, approval behavior, and outcome check. Credentials are configured outside the manifest.
                </Paragraph>
                <pre style={{ overflowX: "auto", padding: 20, background: "#111827", color: "#e5e7eb", borderRadius: 8 }}>
                  {manifest.manifest_yaml}
                </pre>
              </Card>
              <Card title="Model gateway">
                <Descriptions column={1}>
                  <Descriptions.Item label="Mode">{modelStatus?.mode ?? "Loading"}</Descriptions.Item>
                  <Descriptions.Item label="Configured model">{modelStatus?.model ?? "None (local deterministic explanation)"}</Descriptions.Item>
                  <Descriptions.Item label="Setup">Set MODEL_NAME and MODEL_API_KEY in the ignored local .env file, then restart the backend. MODEL_API_BASE is optional for compatible endpoints.</Descriptions.Item>
                </Descriptions>
              </Card>
            </Space>
          ) : (
            <Space direction="vertical" size="large" style={{ display: "flex" }}>
              <Card title="Local printing demo data" extra={<Tag>Read-only inputs</Tag>}>
                <Paragraph>
                  Synthetic data only. No external ERP, MES, credentials, or live customer records are used.
                </Paragraph>
                <Table
                  rowKey="id"
                  dataSource={demoData.orders}
                  pagination={false}
                  scroll={{ x: 850 }}
                  columns={[
                    { title: "Job", dataIndex: "id", key: "id" },
                    { title: "Customer", dataIndex: "customer", key: "customer" },
                    { title: "Product", dataIndex: "product", key: "product" },
                    { title: "Quantity", dataIndex: "quantity", key: "quantity" },
                    { title: "Due day", dataIndex: "due_day", key: "due_day" },
                    { title: "Priority", dataIndex: "priority", key: "priority" },
                    { title: "Material", dataIndex: "required_material", key: "required_material" },
                    { title: "Capability", dataIndex: "required_capability", key: "required_capability" },
                  ]}
                />
              </Card>
              <Row gutter={[16, 16]}>
                {demoData.machines.map((machine) => (
                  <Col xs={24} md={8} key={machine.id}>
                    <Card title={machine.name}>
                      <Paragraph>{machine.capabilities.join(", ")}</Paragraph>
                      <Text>{machine.hours_per_day} available hours/day · {machine.speed_units_per_hour.toLocaleString()} units/hour</Text>
                    </Card>
                  </Col>
                ))}
              </Row>
            </Space>
          )}
        </Content>
      </Layout>
    </Layout>
  );
}
