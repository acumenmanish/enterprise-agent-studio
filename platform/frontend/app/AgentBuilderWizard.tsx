"use client";

import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  List,
  Row,
  Select,
  Space,
  Steps,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import {
  CheckCircleOutlined,
  CloudUploadOutlined,
  DatabaseOutlined,
  PlayCircleOutlined,
  RocketOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import { useEffect, useState } from "react";

const { Paragraph, Text, Title } = Typography;
const API = "/api/backend/api/v1/studio";

export type BuilderModelStatus = {
  configured: boolean;
  model: string | null;
  provider: string | null;
  key_source?: string | null;
};

export type BuilderERPStatus = {
  configured: boolean;
  endpoint_configured: boolean;
  credential_configured: boolean;
  endpoint: string | null;
  key_source: string | null;
  credential_encryption_available: boolean;
};

export type BuilderDocument = { name: string; text: string };
export type BuilderSchedulingConstraints = {
  machine_blackouts: { machine_id: string; day: number }[];
  material_limits: Record<string, number>;
};

function parseSchedulingConstraints(value: unknown): BuilderSchedulingConstraints {
  if (typeof value !== "object" || value === null) {
    throw new Error("Constraints must be a JSON object.");
  }
  const candidate = value as Record<string, unknown>;
  if (
    !Array.isArray(candidate.machine_blackouts) ||
    !candidate.machine_blackouts.every(
      (entry) =>
        typeof entry === "object" &&
        entry !== null &&
        "machine_id" in entry &&
        typeof entry.machine_id === "string" &&
        "day" in entry &&
        Number.isInteger(entry.day) &&
        entry.day >= 0 &&
        entry.day <= 4,
    ) ||
    typeof candidate.material_limits !== "object" ||
    candidate.material_limits === null ||
    Array.isArray(candidate.material_limits) ||
    !Object.values(candidate.material_limits).every(
      (quantity) => Number.isInteger(quantity) && quantity >= 0,
    )
  ) {
    throw new Error("Expected valid machine_blackouts and material_limits values.");
  }
  return {
    machine_blackouts: candidate.machine_blackouts.map((entry) => ({
      machine_id: entry.machine_id,
      day: entry.day,
    })),
    material_limits: candidate.material_limits as Record<string, number>,
  };
}
export type BuilderConfiguration = {
  base_version: string;
  domain: string;
  subdomain: string;
  template_id: string;
  agent_name: string;
  purpose: string;
  instructions: string;
  system_prompt: string;
  business_rules: string;
  enabled_tools: string[];
  scenarios: string[];
  documents: BuilderDocument[];
  approved_constraints: BuilderSchedulingConstraints;
  model_key_override_configured: boolean;
  model_key_override_can_be_saved: boolean;
};

type Props = {
  started: boolean;
  onJourneyStarted: (started: boolean) => void;
  configuration: BuilderConfiguration | null;
  modelStatus: BuilderModelStatus | null;
  erpStatus: BuilderERPStatus | null;
  template: {
    name: string;
    templateName: string;
    objective: string;
    instructions: string;
    tools: string[];
    policies: string[];
    graphNodes: number;
    version: string;
  };
  onConfigurationSaved: (version: string) => Promise<void>;
  onTestRun: (prompt: string) => void;
  onTestConnection: () => Promise<void>;
  onSaveConnection: (endpoint: string, token: string) => Promise<void>;
  onResetConnection: () => Promise<void>;
  connectionTesting: boolean;
  running: boolean;
};

const steps = [
  "Domain & template",
  "Agent brief",
  "Model",
  "API key",
  "Connect data",
  "Policies",
  "Create & test",
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

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error(`Could not encode ${file.name}`));
        return;
      }
      resolve(result.slice(result.indexOf(",") + 1));
    };
    reader.readAsDataURL(file);
  });
}

export default function AgentBuilderWizard({
  started,
  onJourneyStarted,
  configuration,
  modelStatus,
  erpStatus,
  template,
  onConfigurationSaved,
  onTestRun,
  onTestConnection,
  onSaveConnection,
  onResetConnection,
  connectionTesting,
  running,
}: Props) {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<BuilderConfiguration | null>(configuration);
  const [saving, setSaving] = useState(false);
  const [agentName, setAgentName] = useState(template.name);
  const [purpose, setPurpose] = useState(template.objective);
  const [instructions, setInstructions] = useState(template.instructions);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [businessRules, setBusinessRules] = useState("");
  const [scenariosText, setScenariosText] = useState("");
  const [documents, setDocuments] = useState<BuilderDocument[]>([]);
  const [approvedConstraints, setApprovedConstraints] =
    useState<BuilderSchedulingConstraints>({
      machine_blackouts: [],
      material_limits: {},
    });
  const [policyDraft, setPolicyDraft] = useState<string | null>(null);
  const [draftingPolicy, setDraftingPolicy] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [erpEndpoint, setERPEndpoint] = useState("");
  const [erpToken, setERPToken] = useState("");
  const [runPrompt, setRunPrompt] = useState("");
  const [domain, setDomain] = useState("printing");
  const [subdomain, setSubdomain] = useState("production/scheduling");
  const [templateSelected, setTemplateSelected] = useState(true);
  const [enabledTools, setEnabledTools] = useState<string[]>(template.tools);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [messageApi, contextHolder] = message.useMessage();

  useEffect(() => {
    if (!configuration) return;
    setDraft(configuration);
    setAgentName(configuration.agent_name || template.name);
    setPurpose(configuration.purpose || template.objective);
    setInstructions(configuration.instructions || template.instructions);
    setSystemPrompt(configuration.system_prompt);
    setBusinessRules(configuration.business_rules);
    setScenariosText(
      (configuration.scenarios.length
        ? configuration.scenarios
        : [
            "An urgent customer order arrives and should be prioritized without violating hard constraints.",
            "A production press becomes unavailable for one shift.",
          ]
      ).join("\n"),
    );
    setDocuments(configuration.documents);
    setApprovedConstraints(configuration.approved_constraints);
    setDomain(configuration.domain);
    setSubdomain(configuration.subdomain);
    setEnabledTools(configuration.enabled_tools);
  }, [configuration, template.instructions, template.name, template.objective]);

  useEffect(() => {
    if (erpStatus?.endpoint) setERPEndpoint(erpStatus.endpoint);
  }, [erpStatus?.endpoint]);

  const updateDraft = (patch: Partial<BuilderConfiguration>) => {
    setDraft((current) => (current ? { ...current, ...patch } : current));
  };

  const saveConfiguration = async () => {
    if (!draft) return;
    setSaving(true);
    setSaveError(null);
    try {
      const response = await api<{ version: string }>("/agent/configuration", {
        method: "PUT",
        body: JSON.stringify({
          base_version: draft.base_version,
          domain,
          subdomain,
          agent_name: agentName,
          purpose,
          instructions,
          template_id: template.name === "Production Scheduling Agent"
            ? "printing-production-scheduling"
            : draft.template_id,
          system_prompt: systemPrompt,
          business_rules: businessRules,
          enabled_tools: enabledTools,
          scenarios: scenariosText
            .split("\n")
            .map((scenario) => scenario.trim())
            .filter(Boolean),
          documents,
          approved_constraints: approvedConstraints,
        }),
      });
      setDraft((current) =>
        current ? { ...current, base_version: response.version } : current,
      );
      await onConfigurationSaved(response.version);
      messageApi.success(`Agent configuration saved as v${response.version}.`);
      return true;
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Agent configuration could not be saved";
      setSaveError(detail);
      messageApi.error(detail);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const draftPolicyConstraints = async () => {
    const text = [
      businessRules,
      ...documents.map((document) => `Document: ${document.name}\n${document.text}`),
    ]
      .filter(Boolean)
      .join("\n\n");
    if (!text.trim()) {
      messageApi.error("Add business rules or upload a policy document first.");
      return;
    }
    setDraftingPolicy(true);
    try {
      const response = await api<{
        constraints: BuilderSchedulingConstraints;
        requires_user_approval: boolean;
        applied: boolean;
      }>("/agent/policy/draft", {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      setPolicyDraft(JSON.stringify(response.constraints, null, 2));
      messageApi.info("Review the proposed constraints before approving them.");
    } catch (cause) {
      messageApi.error(
        cause instanceof Error ? cause.message : "Could not draft policy constraints",
      );
    } finally {
      setDraftingPolicy(false);
    }
  };

  const approvePolicyDraft = () => {
    if (!policyDraft) return;
    try {
      const parsed: unknown = JSON.parse(policyDraft);
      setApprovedConstraints(parseSchedulingConstraints(parsed));
      setPolicyDraft(null);
      messageApi.success("Policy constraints approved. Save the agent to apply them.");
    } catch (cause) {
      messageApi.error(cause instanceof Error ? cause.message : "Invalid constraint JSON");
    }
  };

  const saveModelKey = async () => {
    if (!apiKey.trim()) {
      messageApi.error("Enter a replacement API key; existing keys are never revealed in the browser.");
      return;
    }
    try {
      await api<{ configured: boolean }>("/model/credential", {
        method: "PUT",
        body: JSON.stringify({ api_key: apiKey }),
      });
      setApiKey("");
      messageApi.success("Agent API key encrypted and saved.");
      await onConfigurationSaved(draft?.base_version ?? template.version);
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "API key could not be saved";
      messageApi.error(detail);
    }
  };

  const revertToEnvironmentModelKey = async () => {
    try {
      await api<{ environment_key_configured: boolean }>("/model/credential", {
        method: "DELETE",
      });
      messageApi.success("The backend environment model key is active again.");
      await onConfigurationSaved(draft?.base_version ?? template.version);
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Could not clear the agent key override";
      messageApi.error(detail);
    }
  };

  const addDocument = async (file: File) => {
    if (documents.length >= 10) {
      messageApi.error("An agent can contain at most 10 knowledge documents.");
      return false;
    }
    if (file.size > 2_000_000) {
      messageApi.error("Knowledge documents must be 2 MB or smaller.");
      return false;
    }
    try {
      const extracted = await api<BuilderDocument>("/agent/documents/extract", {
        method: "POST",
        body: JSON.stringify({
          name: file.name,
          content_base64: await fileToBase64(file),
        }),
      });
      setDocuments((current) => [...current, extracted]);
      messageApi.success(`${file.name} added to local business context.`);
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "Document could not be added";
      messageApi.error(detail);
    }
    return false;
  };

  const saveERPConnection = async () => {
    try {
      await onSaveConnection(erpEndpoint.trim(), erpToken);
      setERPToken("");
    } catch {
      return;
    }
  };

  const resetERPConnection = async () => {
    try {
      await onResetConnection();
    } catch {
      return;
    }
  };

  const proceed = async () => {
    if (step === 1 || step === 5) {
      if (!(await saveConfiguration())) return;
    }
    setStep((current) => Math.min(current + 1, steps.length - 1));
  };

  if (!draft) {
    return <Card loading title="Loading the production scheduling template" />;
  }

  return (
    <Space direction="vertical" size="large" style={{ display: "flex" }}>
      {contextHolder}
      {!started ? (
        <Card
          style={{ maxWidth: 880, margin: "32px auto", textAlign: "center" }}
          styles={{ body: { padding: 40 } }}
        >
          <Tag color="blue">ENTERPRISE AGENT STUDIO</Tag>
          <Title level={2} style={{ marginTop: 20 }}>
            Welcome. Let’s build your production agent.
          </Title>
          <Paragraph type="secondary" style={{ maxWidth: 620, margin: "0 auto 28px" }}>
            Start with a proven manufacturing template, review its purpose and
            instructions, then tailor the model, data, business policies, and
            workflow to your operation.
          </Paragraph>
          <Button
            type="primary"
            size="large"
            icon={<RocketOutlined />}
            onClick={() => onJourneyStarted(true)}
          >
            Start building your agent
          </Button>
          <div style={{ marginTop: 24 }}>
            <Text type="secondary">
              Guided setup · Production Scheduler · Your settings remain editable
            </Text>
          </div>
        </Card>
      ) : (
        <>
          <Card
            title="Create your production scheduling agent"
            extra={<Text type="secondary">Step {step + 1} of {steps.length}</Text>}
          >
            <Steps
              current={step}
              responsive
              onChange={setStep}
              items={steps.map((title) => ({ title }))}
            />
          </Card>

      {step === 0 && (
        <Card title="1 · Select your domain, subdomain, and agent template">
          <Paragraph type="secondary">
            Choose the business area and the prebuilt agent that best matches
            the work you want to improve.
          </Paragraph>
          <Row gutter={16} style={{ marginTop: 16 }}>
            <Col xs={24} md={12}>
              <Text strong>Domain</Text>
              <Select
                value={domain}
                onChange={setDomain}
                style={{ width: "100%", marginTop: 8 }}
                options={[
                  { value: "printing", label: "Manufacturing" },
                ]}
              />
            </Col>
            <Col xs={24} md={12}>
              <Text strong>Subdomain</Text>
              <Select
                value={subdomain}
                onChange={setSubdomain}
                style={{ width: "100%", marginTop: 8 }}
                options={[
                  { value: "production/scheduling", label: "Printing & Packaging" },
                ]}
              />
            </Col>
          </Row>
          <Text strong style={{ display: "block", margin: "24px 0 10px" }}>
            Choose an agent template
          </Text>
          <Card
            hoverable
            onClick={() => setTemplateSelected(true)}
            style={{
              borderColor: templateSelected ? "#1677ff" : undefined,
              background: templateSelected ? "#f0f7ff" : undefined,
            }}
            title={
              <Space>
                <span>{template.templateName}</span>
                <Tag color="blue">Recommended</Tag>
                {templateSelected && <Tag color="green">Selected</Tag>}
              </Space>
            }
            extra={<Tag>{template.version}</Tag>}
          >
            <Paragraph>{template.objective}</Paragraph>
            <Space wrap>
              <Tag>Manufacturing</Tag>
              <Tag>Printing & Packaging</Tag>
              <Tag>Production Scheduling</Tag>
              <Tag>{template.graphNodes} workflow stages</Tag>
            </Space>
          </Card>
          <Alert
            type="info"
            showIcon
            message="Starting with a domain-specific template"
            description="The Production Scheduler comes with a tested optimizer, workflow, instructions, and approval controls. You can review and edit its agent brief in the next step."
            style={{ marginTop: 16 }}
          />
        </Card>
      )}

      {step === 1 && (
        <Card title="2 · Review and personalize your agent">
          <Alert
            type="success"
            showIcon
            message="Your template is ready to customize"
            description="We’ve prefilled this agent from the Production Scheduler template. Review its name, purpose, operating instructions, and example scenarios. Your changes are saved as a new version."
            style={{ marginBottom: 20 }}
          />
          <Space direction="vertical" size="large" style={{ display: "flex" }}>
            <div>
              <Text strong>Agent name</Text>
              <Input
                value={agentName}
                maxLength={200}
                onChange={(event) => setAgentName(event.target.value)}
                style={{ marginTop: 8 }}
              />
            </div>
            <div>
              <Text strong>Purpose</Text>
              <Input.TextArea
                rows={3}
                maxLength={2000}
                value={purpose}
                onChange={(event) => setPurpose(event.target.value)}
                style={{ marginTop: 8 }}
              />
            </div>
            <div>
              <Text strong>Instructions</Text>
              <Input.TextArea
                rows={6}
                maxLength={20_000}
                value={instructions}
                onChange={(event) => setInstructions(event.target.value)}
                style={{ marginTop: 8 }}
              />
              <Text type="secondary">
                Hard optimizer constraints and the planner approval gate remain
                enforced regardless of instruction edits.
              </Text>
            </div>
            <div>
              <Text strong>Template scenarios (one per line)</Text>
              <Paragraph type="secondary">
                These are example situations to help explain the agent and seed
                your evaluation planning. You can edit them now; they are not
                automatically treated as optimizer constraints.
              </Paragraph>
              <Input.TextArea
                rows={4}
                maxLength={20_000}
                value={scenariosText}
                onChange={(event) => setScenariosText(event.target.value)}
              />
            </div>
            <Space wrap>
              <Tag>Printing & Packaging</Tag>
              <Tag>{template.tools.length} template capabilities</Tag>
              <Tag>{template.policies.length} safety policies</Tag>
              <Tag>{template.graphNodes} validated workflow stages</Tag>
            </Space>
          </Space>
        </Card>
      )}

      {step === 2 && (
        <Card title="3 · Choose the inference model">
          <Card type="inner" title="Anthropic Claude" extra={<Tag color="green">Default model</Tag>}>
            <Paragraph>
              The backend uses the configured Anthropic key and pinned default
              model. Model inference interprets your request and explains the
              deterministic result; it never replaces the optimizer.
            </Paragraph>
            <Space wrap>
              <Tag color={modelStatus?.configured ? "green" : "orange"}>
                {modelStatus?.configured
                  ? `${modelStatus.model} · ${modelStatus.key_source ?? "configured"}`
                  : "Anthropic key not detected"}
              </Tag>
              <Tag>Provider: Anthropic</Tag>
            </Space>
            {!modelStatus?.configured && (
              <Alert
                type="warning"
                showIcon
                message="Set ANTHROPIC_API_KEY in the backend .env."
                style={{ marginTop: 16 }}
              />
            )}
          </Card>
        </Card>
      )}

      {step === 3 && (
        <Card title="4 · API key">
          <Alert
            type="success"
            showIcon
            message={
              modelStatus?.key_source === "agent-override"
                ? "This agent is using its encrypted key override."
                : modelStatus?.configured
                  ? "The key configured in the backend .env is active."
                  : "No Anthropic key is configured yet."
            }
            description="For security the existing .env key is never returned to, displayed in, or prefilled in the browser. An optional agent-specific replacement is encrypted at rest and returned only as a configured/not-configured status."
            style={{ marginBottom: 16 }}
          />
          <Input.Password
            aria-label="Agent Anthropic API key override"
            autoComplete="new-password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder="Optional replacement Anthropic API key"
          />
          <Button
            icon={<SaveOutlined />}
            disabled={!apiKey.trim() || !draft.model_key_override_can_be_saved}
            onClick={() => void saveModelKey()}
            style={{ marginTop: 12 }}
          >
            Encrypt and save key for this agent
          </Button>
          {draft.model_key_override_configured && (
            <Button
              danger
              onClick={() => void revertToEnvironmentModelKey()}
              style={{ marginLeft: 8 }}
            >
              Revert to backend .env key
            </Button>
          )}
          {!draft.model_key_override_can_be_saved && (
            <Paragraph type="secondary" style={{ marginTop: 12 }}>
              To enable encrypted per-agent overrides, configure a Fernet
              CREDENTIAL_ENCRYPTION_KEY on the backend. The environment API key
              continues to work without this setting.
            </Paragraph>
          )}
        </Card>
      )}

      {step === 4 && (
        <Card title="5 · Connect production data">
          <Space direction="vertical" size="middle" style={{ display: "flex", marginBottom: 20 }}>
            <div>
              <Text strong>Smart Schedule Query API endpoint</Text>
              <Input
                value={erpEndpoint}
                onChange={(event) => setERPEndpoint(event.target.value)}
                placeholder="https://erp.example.com/ai_agent_query_api.php"
                style={{ marginTop: 8 }}
              />
            </div>
            <div>
              <Text strong>Active ERP bearer token</Text>
              <Input.Password
                autoComplete="new-password"
                value={erpToken}
                onChange={(event) => setERPToken(event.target.value)}
                placeholder={
                  erpStatus?.credential_configured
                    ? "Using configured secret; enter only to replace it"
                    : "Paste the active ERP-issued bearer token"
                }
                style={{ marginTop: 8 }}
              />
              <Text type="secondary">
                The existing token is never read back into the browser. New
                credentials require CREDENTIAL_ENCRYPTION_KEY and are encrypted
                before storage.
              </Text>
            </div>
            {!erpStatus?.credential_encryption_available && (
              <Alert
                type="warning"
                showIcon
                message="Set CREDENTIAL_ENCRYPTION_KEY in the backend .env to save a new connection."
              />
            )}
            <Space wrap>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                disabled={
                  !erpEndpoint.trim()
                  || !erpToken.trim()
                  || !erpStatus?.credential_encryption_available
                }
                onClick={() => void saveERPConnection()}
              >
                Save encrypted connection
              </Button>
              <Button
                disabled={!erpStatus?.key_source || erpStatus.key_source === "environment"}
                onClick={() => void resetERPConnection()}
              >
                Revert to backend .env connection
              </Button>
            </Space>
          </Space>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={8}>
              <Card type="inner" title="REST API connector" extra={<Tag color="green">MVP</Tag>}>
                Smart Schedule Query API
                <div><Text type="secondary">Orders · machines · operations · existing schedule</Text></div>
              </Card>
            </Col>
            <Col xs={24} md={8}>
              <Card type="inner" title="MCP server" extra={<Tag>Later</Tag>}>
                Governed capability gateway
                <div><Text type="secondary">No MCP server is configured in this local MVP.</Text></div>
              </Card>
            </Col>
            <Col xs={24} md={8}>
              <Card type="inner" title="SQL Server" extra={<Tag>Later</Tag>}>
                Read-only SQL connector
                <div><Text type="secondary">Not exposed by the shared ERP API contract.</Text></div>
              </Card>
            </Col>
          </Row>
          <Alert
            type="info"
            showIcon
            message="Live source preview and optimizer inputs are separate."
            description="The current API exposes safe read-only previews, but not the inventory/changeover inputs required by the optimizer; maintenance is disabled. Test the connection below. Runs continue to use synthetic data until those mappings are available."
            style={{ marginTop: 16 }}
          />
          <Space wrap style={{ marginTop: 12 }}>
            <Tag color={erpStatus?.configured ? "green" : "default"}>
              {erpStatus?.configured ? "ERP endpoint and token configured" : "ERP connection not configured"}
            </Tag>
            <Button
              icon={<DatabaseOutlined />}
              disabled={!erpStatus?.configured}
              loading={connectionTesting}
              onClick={() => void onTestConnection()}
            >
              Test API connection
            </Button>
          </Space>
        </Card>
      )}

      {step === 5 && (
        <Card title="6 · Add your system prompt, policies, and rules">
          <Space direction="vertical" size="middle" style={{ display: "flex" }}>
            <div>
              <Text strong>Customize the template system prompt</Text>
              <Input.TextArea
                rows={4}
                maxLength={20_000}
                value={systemPrompt}
                onChange={(event) => setSystemPrompt(event.target.value)}
                placeholder="Optional domain-specific instructions. The template instructions and hard safety rules remain in force."
                style={{ marginTop: 8 }}
              />
            </div>
            <div>
              <Text strong>Business-specific rules</Text>
              <Input.TextArea
                rows={4}
                maxLength={20_000}
                value={businessRules}
                onChange={(event) => setBusinessRules(event.target.value)}
                placeholder="e.g. Prioritize pharmaceutical jobs; avoid press changeovers after 18:00."
                style={{ marginTop: 8 }}
              />
            </div>
            <div>
              <Text strong>Knowledge documents for local retrieval</Text>
              <Paragraph type="secondary">
                Add UTF-8 text, Markdown, or text-based PDF rulebooks (maximum
                2 MB each). Text is stored with this tenant agent and the most
                relevant passages are retrieved for prompt interpretation and
                explanation; retrieved policy text does not override hard
                optimizer constraints.
              </Paragraph>
              <Upload
                accept=".txt,.md,.pdf"
                showUploadList={false}
                beforeUpload={(file) => {
                  void addDocument(file);
                  return false;
                }}
              >
                <Button icon={<CloudUploadOutlined />}>Upload policy or SOP</Button>
              </Upload>
              {documents.length > 0 && (
                <List
                  size="small"
                  dataSource={documents}
                  renderItem={(document, index) => (
                    <List.Item
                      actions={[
                        <Button
                          key="remove"
                          type="link"
                          danger
                          onClick={() =>
                            setDocuments((current) => current.filter((_, i) => i !== index))
                          }
                        >
                          Remove
                        </Button>,
                      ]}
                    >
                      <Space direction="vertical" size={0}>
                        <Text strong>{document.name}</Text>
                        <Text type="secondary">{document.text.length.toLocaleString()} characters indexed locally</Text>
                      </Space>
                    </List.Item>
                  )}
                />
              )}
            </div>
            <Card
              size="small"
              title="Review optimizer constraints extracted from policy"
              extra={
                <Button loading={draftingPolicy} onClick={() => void draftPolicyConstraints()}>
                  Draft constraints
                </Button>
              }
            >
              <Paragraph type="secondary">
                The model can propose machine blackouts and material limits. Nothing
                changes the optimizer until you review and approve the structured
                draft. Ambiguous or unsupported statements remain context only.
              </Paragraph>
              {policyDraft !== null && (
                <Space direction="vertical" style={{ display: "flex" }}>
                  <Input.TextArea
                    rows={6}
                    aria-label="Review extracted scheduling constraints"
                    value={policyDraft}
                    onChange={(event) => setPolicyDraft(event.target.value)}
                  />
                  <Space>
                    <Button type="primary" onClick={approvePolicyDraft}>
                      Approve constraints
                    </Button>
                    <Button onClick={() => setPolicyDraft(null)}>Discard draft</Button>
                  </Space>
                </Space>
              )}
              {(approvedConstraints.machine_blackouts.length > 0 ||
                Object.keys(approvedConstraints.material_limits).length > 0) && (
                <Alert
                  type="success"
                  showIcon
                  message="Approved optimizer constraints"
                  description={JSON.stringify(approvedConstraints)}
                  style={{ marginTop: 12 }}
                />
              )}
            </Card>
            <div>
              <Text strong>Template tools (remove tools you do not want enabled)</Text>
              <Select
                mode="multiple"
                value={enabledTools}
                onChange={(tools: string[]) => setEnabledTools(tools)}
                options={template.tools.map((tool) => ({
                  value: tool,
                  label: tool.replace("@1.0.0", "").replaceAll("_", " "),
                }))}
                style={{ width: "100%", marginTop: 8 }}
              />
              <Text type="secondary">
                Order, capacity, and simulation tools are needed for schedule
                runs. Remove publish_schedule to disable approval/publish actions.
              </Text>
            </div>
            {saveError && <Alert type="error" showIcon message={saveError} />}
          </Space>
        </Card>
      )}

      {step === 6 && (
        <Card title="7 · Save, edit the Pro Canvas, and test your agent">
          <Alert
            type="success"
            showIcon
            message={`Template ready · ${template.graphNodes} typed nodes · ${enabledTools.length} tools enabled`}
            description="Your saved instructions, business rules, examples, and uploaded documents are used by the backend when you run a test. Schedule calculation remains deterministic and approval-gated."
            style={{ marginBottom: 16 }}
          />
          <Space direction="vertical" style={{ display: "flex" }}>
            <Title level={5}>Run a test prompt</Title>
            <Input.TextArea
              rows={3}
              maxLength={1000}
              value={runPrompt}
              onChange={(event) => setRunPrompt(event.target.value)}
              placeholder="Describe the production schedule to test."
            />
            <Space wrap>
              <Button
                icon={<SaveOutlined />}
                loading={saving}
                onClick={() => void saveConfiguration()}
              >
                Save agent configuration
              </Button>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={running}
                disabled={!runPrompt.trim()}
                onClick={() => onTestRun(runPrompt)}
              >
                Run test
              </Button>
            </Space>
            <Paragraph type="secondary">
              The current schedule tool uses the local demo order and machine
              dataset; the prompt affects model intent/explanation and retrieved
              context, not feasibility rules or live ERP schedule inputs.
            </Paragraph>
          </Space>
        </Card>
      )}

      <Card>
        <Space style={{ display: "flex", justifyContent: "space-between" }} wrap>
          <Button
            onClick={() => {
              if (step === 0) {
                onJourneyStarted(false);
              }
              else setStep((current) => Math.max(0, current - 1));
            }}
          >
            Back
          </Button>
          {step < steps.length - 1 ? (
            <Button
              type="primary"
              disabled={
                (step === 0 && !templateSelected) ||
                (step === 1 && (!agentName.trim() || !purpose.trim()))
              }
              onClick={() => void proceed()}
            >
              {step === 1 || step === 5 ? "Save and continue" : "Continue"}
            </Button>
          ) : (
            <Button
              icon={<CheckCircleOutlined />}
              onClick={() => {
                onJourneyStarted(false);
                setStep(0);
              }}
            >
              Start another setup
            </Button>
          )}
        </Space>
      </Card>
        </>
      )}
    </Space>
  );
}
