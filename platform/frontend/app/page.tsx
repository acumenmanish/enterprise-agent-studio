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
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";
import AgentBuilderWizard, {
  type BuilderConfiguration,
  type BuilderERPStatus,
  type BuilderModelStatus,
} from "./AgentBuilderWizard";
import WorkflowCanvas, { type WorkflowDefinition } from "./WorkflowCanvas";

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
        inputs: {
          type: "object";
          properties: Record<string, { type: string }>;
          required: string[];
        };
        outputs: {
          type: "object";
          properties: Record<string, { type: string }>;
          required: string[];
        };
      }[];
      edges: { from: string; to: string }[];
    };
  };
  model_configured: boolean;
};

type ManifestRevision = {
  commit: string;
  created_at: string;
  message: string;
  version: string;
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

type ModelStatus = BuilderModelStatus & { mode: string };
type ERPStatus = BuilderERPStatus;
type ERPPreview = {
  connected: boolean;
  read_only: boolean;
  preview_limit: number;
  datasets: {
    alias: string;
    count: number;
    total: number;
    has_more: boolean;
    records: Record<string, unknown>[];
  }[];
  data_gaps: { entity: string; available: boolean; reason: string }[];
};
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
  { key: "data", label: "Data Connections", icon: <DatabaseOutlined /> },
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
  const [manifestDraft, setManifestDraft] = useState("");
  const [manifestEditing, setManifestEditing] = useState(false);
  const [manifestChangeSummary, setManifestChangeSummary] = useState("");
  const [manifestErrors, setManifestErrors] = useState<string[]>([]);
  const [manifestHistory, setManifestHistory] = useState<ManifestRevision[]>([]);
  const [compareFrom, setCompareFrom] = useState<string>();
  const [compareTo, setCompareTo] = useState<string>();
  const [manifestDiff, setManifestDiff] = useState<string | null>(null);
  const [manifestSaving, setManifestSaving] = useState(false);
  const [manifestComparing, setManifestComparing] = useState(false);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [erpStatus, setERPStatus] = useState<ERPStatus | null>(null);
  const [agentConfiguration, setAgentConfiguration] =
    useState<BuilderConfiguration | null>(null);
  const [erpPreview, setERPPreview] = useState<ERPPreview | null>(null);
  const [erpTesting, setERPTesting] = useState(false);
  const [workflowSaving, setWorkflowSaving] = useState(false);
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
  const manifestFileInput = useRef<HTMLInputElement>(null);

  const refreshRuns = useCallback(async () => {
    setRuns(await api<RunSummary[]>("/runs"));
  }, []);

  const loadInitial = useCallback(async () => {
    setInitialLoading(true);
    setError(null);
    setERPPreview(null);
    try {
      const [
        manifestResponse,
        modelResponse,
        erpStatusResponse,
        configurationResponse,
        dataResponse,
        runResponse,
        history,
      ] =
        await Promise.all([
          api<Manifest>("/manifest"),
          api<ModelStatus>("/model/status"),
          api<ERPStatus>("/data/erp/status"),
          api<BuilderConfiguration>("/agent/configuration"),
          api<DemoData>("/demo-data"),
          api<RunSummary[]>("/runs"),
          api<ManifestRevision[]>("/manifest/history"),
        ]);
      setManifest(manifestResponse);
      setManifestDraft(manifestResponse.manifest_yaml);
      setModelStatus(modelResponse);
      setERPStatus(erpStatusResponse);
      setAgentConfiguration(configurationResponse);
      setDemoData(dataResponse);
      setRuns(runResponse);
      setManifestHistory(history);
      setCompareFrom(history[1]?.commit ?? history[0]?.commit);
      setCompareTo(history[0]?.commit);
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

  const testERPConnection = async () => {
    setERPTesting(true);
    setError(null);
    setERPPreview(null);
    try {
      setERPStatus(await api<ERPStatus>("/data/erp/status"));
      const preview = await api<ERPPreview>("/data/erp/preview", { method: "POST" });
      setERPPreview(preview);
      messageApi.success("ERP connection verified. Read-only source preview is ready.");
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "ERP connection failed";
      setError(detail);
      messageApi.error(detail);
    } finally {
      setERPTesting(false);
    }
  };

  const saveERPConnection = async (endpoint: string, token: string) => {
    setError(null);
    try {
      await api<{ configured: boolean }>("/data/erp/connection", {
        method: "PUT",
        body: JSON.stringify({ endpoint, api_token: token }),
      });
      setERPStatus(await api<ERPStatus>("/data/erp/status"));
      messageApi.success("ERP endpoint and encrypted bearer token saved.");
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "ERP connection could not be saved";
      setError(detail);
      messageApi.error(detail);
      throw cause;
    }
  };

  const resetERPConnection = async () => {
    setError(null);
    try {
      await api<{ environment_connection_configured: boolean }>(
        "/data/erp/connection",
        { method: "DELETE" },
      );
      setERPStatus(await api<ERPStatus>("/data/erp/status"));
      setERPPreview(null);
      messageApi.success("Reverted to the backend .env ERP connection.");
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "ERP connection reset failed";
      setError(detail);
      messageApi.error(detail);
      throw cause;
    }
  };

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

  const createSchedule = async (promptText = requestText) => {
    setRunning(true);
    setError(null);
    try {
      const response = await api<{ run_id: string }>("/schedule/run", {
        method: "POST",
        body: JSON.stringify({
          planning_horizon_days: planningDays,
          objective,
          request_text: promptText || null,
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

  const refreshAgentConfiguration = async () => {
    const [manifestResponse, configurationResponse, modelResponse, history] =
      await Promise.all([
        api<Manifest>("/manifest"),
        api<BuilderConfiguration>("/agent/configuration"),
        api<ModelStatus>("/model/status"),
        api<ManifestRevision[]>("/manifest/history"),
      ]);
    setManifest(manifestResponse);
    setManifestDraft(manifestResponse.manifest_yaml);
    setAgentConfiguration(configurationResponse);
    setModelStatus(modelResponse);
    setManifestHistory(history);
    setCompareFrom(history[1]?.commit ?? history[0]?.commit);
    setCompareTo(history[0]?.commit);
  };

  const saveWorkflowGraph = async (graph: WorkflowDefinition) => {
    if (!manifest) return;
    setWorkflowSaving(true);
    setError(null);
    try {
      const response = await api<{
        manifest: Manifest["manifest"];
        manifest_yaml: string;
      }>("/manifest/graph", {
        method: "PUT",
        body: JSON.stringify({
          graph,
          base_version: manifest.manifest.agent.version,
          change_summary: "Edit production scheduling workflow canvas",
        }),
      });
      setManifest({ ...manifest, manifest: response.manifest, manifest_yaml: response.manifest_yaml });
      setManifestDraft(response.manifest_yaml);
      const history = await api<ManifestRevision[]>("/manifest/history");
      setManifestHistory(history);
      await refreshAgentConfiguration();
      messageApi.success(`Workflow validated and saved as v${response.manifest.agent.version}.`);
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Workflow save failed";
      setError(detail);
      messageApi.error(detail);
    } finally {
      setWorkflowSaving(false);
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

  const validateManifestDraft = async (): Promise<boolean> => {
    try {
      const result = await api<{ valid: boolean; errors: string[] }>("/manifest/validate", {
        method: "POST",
        body: JSON.stringify({ manifest_yaml: manifestDraft }),
      });
      setManifestErrors(result.errors);
      if (result.valid) {
        messageApi.success("Manifest YAML and typed workflow contracts are valid.");
      } else {
        messageApi.error("Manifest validation failed.");
      }
      return result.valid;
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Manifest validation failed";
      setManifestErrors([detail]);
      messageApi.error(detail);
      return false;
    }
  };

  const saveManifestDraft = async () => {
    if (!manifest || !manifestChangeSummary.trim()) {
      messageApi.error("Add a short change summary before saving a manifest version.");
      return;
    }
    setManifestSaving(true);
    setManifestErrors([]);
    try {
      const validation = await api<{ valid: boolean; errors: string[] }>("/manifest/validate", {
        method: "POST",
        body: JSON.stringify({ manifest_yaml: manifestDraft }),
      });
      setManifestErrors(validation.errors);
      if (!validation.valid) {
        messageApi.error("Fix the manifest validation errors before saving.");
        return;
      }
      const saved = await api<{
        manifest: Manifest["manifest"];
        manifest_yaml: string;
        revision: string;
      }>("/manifest", {
        method: "PUT",
        body: JSON.stringify({
          manifest_yaml: manifestDraft,
          base_version: manifest.manifest.agent.version,
          change_summary: manifestChangeSummary.trim(),
        }),
      });
      setManifest({ ...manifest, manifest: saved.manifest, manifest_yaml: saved.manifest_yaml });
      setManifestDraft(saved.manifest_yaml);
      setManifestChangeSummary("");
      setManifestEditing(false);
      setManifestDiff(null);
      const history = await api<ManifestRevision[]>("/manifest/history");
      setManifestHistory(history);
      setCompareFrom(history[1]?.commit ?? history[0]?.commit);
      setCompareTo(history[0]?.commit);
      messageApi.success(`Saved manifest v${saved.manifest.agent.version} to the local Git repository.`);
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Manifest save failed";
      setError(detail);
      messageApi.error(detail);
    } finally {
      setManifestSaving(false);
    }
  };

  const compareManifestRevisions = async () => {
    if (!compareFrom || !compareTo) return;
    setManifestComparing(true);
    setError(null);
    try {
      const query = new URLSearchParams({
        from_revision: compareFrom,
        to_revision: compareTo,
      });
      const result = await api<{ diff: string }>(`/manifest/compare?${query.toString()}`);
      setManifestDiff(result.diff);
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Manifest comparison failed";
      setError(detail);
      messageApi.error(detail);
    } finally {
      setManifestComparing(false);
    }
  };

  const importManifestFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!file) return;
    try {
      setManifestDraft(await file.text());
      setManifestErrors([]);
      setManifestEditing(true);
      setManifestDiff(null);
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Unable to read manifest file";
      setError(detail);
    }
  };

  const exportManifest = () => {
    const blob = new Blob([manifestDraft], { type: "application/yaml" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${manifest?.manifest.agent.id ?? "agent"}-manifest.yaml`;
    link.click();
    URL.revokeObjectURL(url);
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
                      <AgentBuilderWizard
                        configuration={agentConfiguration}
                        modelStatus={modelStatus}
                        erpStatus={erpStatus}
                        template={{
                          name: manifest.manifest.agent.name,
                          objective: manifest.manifest.agent.objective,
                          tools: manifest.manifest.tools,
                          policies: manifest.manifest.policies,
                          graphNodes: manifest.manifest.execution_graph.nodes.length,
                          version: manifest.manifest.agent.version,
                        }}
                        onConfigurationSaved={refreshAgentConfiguration}
                        onTestRun={(prompt) => void createSchedule(prompt)}
                        onTestConnection={testERPConnection}
                        onSaveConnection={saveERPConnection}
                        onResetConnection={resetERPConnection}
                        connectionTesting={erpTesting}
                        running={running}
                      />
                    ),
                  },
                  {
                    key: "pro-canvas",
                    label: "Pro Canvas",
                    children: (
                      <Space direction="vertical" size="large" style={{ display: "flex" }}>
                        <Card
                          title="Typed execution graph"
                          extra={<Tag color="green">Editable manifest-backed workflow</Tag>}
                        >
                          <WorkflowCanvas
                            key={manifest.manifest.agent.version}
                            graph={manifest.manifest.execution_graph}
                            onSave={(graph) => void saveWorkflowGraph(graph)}
                            saving={workflowSaving}
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
              <Card
                title={
                  <Space>
                    <span>Portable agent manifest</span>
                    <Tag color="green">v{manifest.manifest.agent.version}</Tag>
                  </Space>
                }
                extra={
                  <Space wrap>
                    <Button onClick={exportManifest}>Export YAML</Button>
                    <Button onClick={() => manifestFileInput.current?.click()}>Import YAML</Button>
                    {!manifestEditing ? (
                      <Button type="primary" onClick={() => setManifestEditing(true)}>
                        Edit manifest
                      </Button>
                    ) : (
                      <>
                        <Button
                          onClick={() => {
                            setManifestDraft(manifest.manifest_yaml);
                            setManifestErrors([]);
                            setManifestEditing(false);
                          }}
                        >
                          Cancel
                        </Button>
                        <Button onClick={() => void validateManifestDraft()}>
                          Validate
                        </Button>
                      </>
                    )}
                  </Space>
                }
              >
                <input
                  ref={manifestFileInput}
                  type="file"
                  accept=".yaml,.yml,application/yaml,text/yaml"
                  onChange={(event) => void importManifestFile(event)}
                  style={{ display: "none" }}
                />
                <Paragraph>
                  The version-controlled YAML is the source of truth for the agent configuration. Edit or import a portable manifest, validate its typed graph, and save a new immutable local Git version. Credentials stay outside the manifest.
                </Paragraph>
                {manifestEditing ? (
                  <Space direction="vertical" style={{ display: "flex" }} size="middle">
                    <Input.TextArea
                      aria-label="Agent manifest YAML"
                      value={manifestDraft}
                      onChange={(event) => {
                        setManifestDraft(event.target.value);
                        setManifestErrors([]);
                      }}
                      autoSize={{ minRows: 22, maxRows: 42 }}
                      spellCheck={false}
                      style={{ fontFamily: "monospace" }}
                    />
                    <Input
                      aria-label="Manifest change summary"
                      placeholder="Change summary (required for version history)"
                      maxLength={500}
                      value={manifestChangeSummary}
                      onChange={(event) => setManifestChangeSummary(event.target.value)}
                    />
                    {manifestErrors.length > 0 && (
                      <Alert
                        type="error"
                        showIcon
                        message="Manifest validation errors"
                        description={
                          <ul style={{ margin: 0, paddingLeft: 20 }}>
                            {manifestErrors.map((validationError, index) => (
                              <li key={`${index}-${validationError}`}>{validationError}</li>
                            ))}
                          </ul>
                        }
                      />
                    )}
                    <Button
                      type="primary"
                      loading={manifestSaving}
                      onClick={() => void saveManifestDraft()}
                    >
                      Validate and save new version
                    </Button>
                  </Space>
                ) : (
                  <pre style={{ overflowX: "auto", padding: 20, background: "#111827", color: "#e5e7eb", borderRadius: 8 }}>
                    {manifest.manifest_yaml}
                  </pre>
                )}
              </Card>
              <Card title="Immutable local version history">
                {manifestHistory.length === 0 ? (
                  <Empty description="No committed manifest versions" />
                ) : (
                  <List
                    dataSource={manifestHistory}
                    renderItem={(revision) => (
                      <List.Item>
                        <Space direction="vertical" size={0}>
                          <Text strong>v{revision.version} · {revision.message}</Text>
                          <Text type="secondary">
                            {new Date(revision.created_at).toLocaleString()} · {revision.commit.slice(0, 12)}
                          </Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                )}
              </Card>
              <Card title="Compare manifest versions">
                <Space wrap style={{ width: "100%" }}>
                  <Select
                    aria-label="Compare from version"
                    placeholder="From version"
                    value={compareFrom}
                    onChange={setCompareFrom}
                    options={manifestHistory.map((revision) => ({
                      value: revision.commit,
                      label: `v${revision.version} · ${revision.message}`,
                    }))}
                    style={{ minWidth: 220, flex: 1 }}
                  />
                  <Select
                    aria-label="Compare to version"
                    placeholder="To version"
                    value={compareTo}
                    onChange={setCompareTo}
                    options={manifestHistory.map((revision) => ({
                      value: revision.commit,
                      label: `v${revision.version} · ${revision.message}`,
                    }))}
                    style={{ minWidth: 220, flex: 1 }}
                  />
                  <Button
                    type="primary"
                    loading={manifestComparing}
                    disabled={manifestHistory.length < 2 || !compareFrom || !compareTo}
                    onClick={() => void compareManifestRevisions()}
                  >
                    Compare
                  </Button>
                </Space>
                {manifestDiff !== null && (
                  <pre style={{ overflowX: "auto", padding: 20, background: "#111827", color: "#e5e7eb", borderRadius: 8, marginTop: 16 }}>
                    {manifestDiff || "These manifest versions are identical."}
                  </pre>
                )}
              </Card>
              <Card title="Model gateway">
                <Descriptions column={1}>
                  <Descriptions.Item label="Mode">{modelStatus?.mode ?? "Loading"}</Descriptions.Item>
                  <Descriptions.Item label="Configured model">{modelStatus?.model ?? "None (local deterministic explanation)"}</Descriptions.Item>
                  <Descriptions.Item label="Provider">{modelStatus?.provider ?? "Not configured"}</Descriptions.Item>
                  <Descriptions.Item label="Setup">
                    The backend reads ANTHROPIC_API_KEY from the ignored local .env file and uses claude-sonnet-4-5 by default. MODEL_NAME can pin another Anthropic model. Existing OpenAI-compatible endpoints remain supported through MODEL_NAME, MODEL_API_KEY, and MODEL_API_BASE. Keys never enter the browser or agent manifest.
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Space>
          ) : (
            <Space direction="vertical" size="large" style={{ display: "flex" }}>
              <Card
                title="ERP Query API · read-only connection"
                extra={
                  <Tag color={erpStatus?.configured ? "green" : "default"}>
                    {erpStatus?.configured ? "Credentials configured" : "Not configured"}
                  </Tag>
                }
              >
                <Paragraph>
                  Connect using the documented server-to-server API. Configure the
                  endpoint and active bearer token in the Quick Build data step;
                  environment-level ERP_QUERY_API_URL and ERP_API_TOKEN are also
                  supported. The token is encrypted at rest, never returned to the
                  browser, and never saved in the agent manifest.
                </Paragraph>
                <Alert
                  type="info"
                  showIcon
                  message="Read-only preview only"
                  description="This connection verifies the orders, machines, operations, and schedule aliases. Live schedule generation is not enabled yet: the API docs do not expose inventory or changeover data, and the maintenance alias is disabled. The optimizer continues to use synthetic data until those gaps and field mappings are validated."
                  style={{ marginBottom: 16 }}
                />
                <Space wrap>
                  <Tag>
                    Endpoint: {erpStatus?.endpoint_configured ? "configured" : "missing"}
                  </Tag>
                  <Tag>
                    Bearer token: {erpStatus?.credential_configured ? "configured" : "missing"}
                  </Tag>
                  <Button
                    type="primary"
                    icon={<DatabaseOutlined />}
                    loading={erpTesting}
                    disabled={!erpStatus?.configured}
                    onClick={() => void testERPConnection()}
                  >
                    Test connection and preview data
                  </Button>
                </Space>
              </Card>
              {erpPreview && (
                <>
                  <Card title="Live source preview" extra={<Tag color="blue">Read only</Tag>}>
                    <Row gutter={[12, 12]}>
                      {erpPreview.datasets.map((dataset) => (
                        <Col xs={24} key={dataset.alias}>
                          <Card
                            type="inner"
                            title={`${dataset.alias} · ${dataset.total.toLocaleString()} records`}
                            extra={dataset.has_more ? `First ${dataset.count} shown` : undefined}
                          >
                            {dataset.records.length > 0 ? (
                              <Table<Record<string, unknown>>
                                size="small"
                                pagination={false}
                                scroll={{ x: 700 }}
                                rowKey={(_, index) => `${dataset.alias}-${index}`}
                                dataSource={dataset.records}
                                columns={Object.keys(dataset.records[0]).map((field) => ({
                                  title: field,
                                  dataIndex: field,
                                  key: field,
                                  render: (value: unknown) =>
                                    value == null
                                      ? "—"
                                      : typeof value === "object"
                                        ? JSON.stringify(value)
                                        : String(value),
                                }))}
                              />
                            ) : (
                              <Empty description="No records returned for this alias" />
                            )}
                          </Card>
                        </Col>
                      ))}
                    </Row>
                  </Card>
                  <Card title="Scheduler data requirements">
                    <List
                      dataSource={erpPreview.data_gaps}
                      renderItem={(gap) => (
                        <List.Item>
                          <Space direction="vertical" size={0}>
                            <Text strong>{gap.entity}</Text>
                            <Text type="secondary">{gap.reason}</Text>
                          </Space>
                          <Tag color={gap.available ? "green" : "gold"}>
                            {gap.available ? "Available" : "Mapping required"}
                          </Tag>
                        </List.Item>
                      )}
                    />
                  </Card>
                </>
              )}
              <Card title="Local printing demo data" extra={<Tag>Read-only inputs</Tag>}>
                <Paragraph>
                  Synthetic fallback data used by the current optimizer and evaluation suite. A successful ERP preview does not change schedule inputs.
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
