from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCHEDULING_TOOLS = {
    "get_open_orders@1.0.0",
    "get_machine_capacity@1.0.0",
    "simulate_schedule@1.0.0",
    "publish_schedule@1.0.0",
}


class ScheduleRequest(BaseModel):
    planning_horizon_days: int = Field(default=5, ge=1, le=5)
    objective: Literal["balanced", "due_date", "changeover"] = "balanced"
    request_text: str | None = Field(default=None, max_length=1000)


class ScheduleIntent(BaseModel):
    planning_horizon_days: int = Field(ge=1, le=5)
    objective: Literal["balanced", "due_date", "changeover"]


class KnowledgeDocument(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=250_000)


class KnowledgeDocumentUpload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1, max_length=3_000_000)


class AgentConfigurationUpdate(BaseModel):
    base_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    domain: Literal["printing"] = "printing"
    subdomain: Literal["production/scheduling"] = "production/scheduling"
    template_id: Literal["printing-production-scheduling"] = "printing-production-scheduling"
    system_prompt: str = Field(default="", max_length=20_000)
    business_rules: str = Field(default="", max_length=20_000)
    enabled_tools: list[str] = Field(default_factory=list, max_length=20)
    scenarios: list[str] = Field(default_factory=list, max_length=50)
    documents: list[KnowledgeDocument] = Field(default_factory=list, max_length=10)

    @field_validator("enabled_tools")
    @classmethod
    def validate_enabled_tools(cls, tools: list[str]) -> list[str]:
        unknown = sorted(set(tools) - SCHEDULING_TOOLS)
        if unknown:
            raise ValueError("Unsupported production scheduling tool: " + ", ".join(unknown))
        if len(set(tools)) != len(tools):
            raise ValueError("Tools must not contain duplicates")
        return tools

    @field_validator("scenarios")
    @classmethod
    def validate_scenarios(cls, scenarios: list[str]) -> list[str]:
        if any(len(scenario) > 2_000 for scenario in scenarios):
            raise ValueError("Each scenario must be 2000 characters or fewer")
        return scenarios

    @field_validator("documents")
    @classmethod
    def validate_document_size(cls, documents: list[KnowledgeDocument]) -> list[KnowledgeDocument]:
        if sum(len(document.text) for document in documents) > 1_000_000:
            raise ValueError("Total document text must be 1 MB or less")
        return documents


class AgentConfigurationResponse(AgentConfigurationUpdate):
    updated_at: str | None = None
    model_key_override_configured: bool = False
    model_key_override_can_be_saved: bool = False


class ModelCredentialUpdate(BaseModel):
    api_key: str = Field(min_length=1, max_length=500)


class ERPConnectionUpdate(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2000)
    api_token: str = Field(min_length=1, max_length=5000)


class WorkflowGraphSaveRequest(BaseModel):
    graph: dict
    base_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    change_summary: str = Field(min_length=1, max_length=500)


class ApprovalDecision(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    comment: str | None = Field(default=None, max_length=2000)


class ManifestValidationRequest(BaseModel):
    manifest_yaml: str = Field(min_length=1, max_length=1_000_000)


class ManifestSaveRequest(ManifestValidationRequest):
    base_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    change_summary: str = Field(min_length=1, max_length=500)


class ManifestResponse(BaseModel):
    manifest: dict


class ScheduleRunResponse(BaseModel):
    run_id: str
    status: str
    result: dict


class RunSummary(BaseModel):
    id: str
    agent_id: str
    status: str
    created_at: str
    result: dict | None
