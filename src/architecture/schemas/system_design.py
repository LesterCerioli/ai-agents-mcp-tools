import uuid
from enum import Enum

from pydantic import BaseModel, Field


class CommunicationStyle(str, Enum):
    SYNC_REST = "sync_rest"
    SYNC_GRPC = "sync_grpc"
    ASYNC_EVENT = "async_event"
    ASYNC_MESSAGE = "async_message"


class ApiGatewayType(str, Enum):
    SINGLE = "single"
    BFF = "bff"
    FEDERATED = "federated"


class DataDistributionPattern(str, Enum):
    DATABASE_PER_SERVICE = "database_per_service"
    CQRS = "cqrs"
    EVENT_SOURCING = "event_sourcing"
    SHARED_DATABASE = "shared_database"


class PortType(str, Enum):
    DRIVING = "driving"
    DRIVEN = "driven"


class MonolithLayering(str, Enum):
    LAYERED = "layered"
    MODULAR = "modular"
    VERTICAL_SLICES = "vertical_slices"


# ─── Microservices ────────────────────────────────────────────────────────────

class ServiceContract(BaseModel):
    service_name: str
    owner_domain: str
    sla: str = "99.9%"
    protocols: list[str] = Field(default_factory=list)
    schema_summary: str = ""
    owner_team: str = ""


class BoundedContext(BaseModel):
    name: str
    service_name: str
    subdomain: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    communication_style: CommunicationStyle = CommunicationStyle.SYNC_REST
    database_strategy: DataDistributionPattern = DataDistributionPattern.DATABASE_PER_SERVICE
    technology_hints: list[str] = Field(default_factory=list)


class ApiGatewayRecommendation(BaseModel):
    gateway_type: ApiGatewayType
    rationale: str
    technology_hints: list[str] = Field(default_factory=list)
    bff_clients: list[str] = Field(default_factory=list)


class ServiceMeshRecommendation(BaseModel):
    required: bool
    rationale: str
    mesh_technology: list[str] = Field(default_factory=list)
    services_count: int = 0


class DistributedDataStrategy(BaseModel):
    pattern: DataDistributionPattern
    rationale: str
    event_bus: str | None = None
    cqrs_stores: list[str] = Field(default_factory=list)


class MicroservicesSystemDesign(BaseModel):
    design_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str
    bounded_contexts: list[BoundedContext]
    api_gateway: ApiGatewayRecommendation
    service_mesh: ServiceMeshRecommendation
    data_strategy: DistributedDataStrategy
    service_contracts: list[ServiceContract]
    rationale: str = ""
    design_confidence: float = Field(default=0.8, ge=0.0, le=1.0)


# ─── Hexagonal ────────────────────────────────────────────────────────────────

class HexagonalPort(BaseModel):
    name: str
    port_type: PortType
    interface_name: str
    description: str = ""
    adapter_implementations: list[str] = Field(default_factory=list)


class HexagonalDomainService(BaseModel):
    name: str
    responsibilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class HexagonalSystemDesign(BaseModel):
    design_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str
    domain_services: list[HexagonalDomainService]
    driving_ports: list[HexagonalPort]
    driven_ports: list[HexagonalPort]
    anti_corruption_layers: list[str] = Field(default_factory=list)
    technology_adapters: dict[str, list[str]] = Field(default_factory=dict)
    rationale: str = ""
    design_confidence: float = Field(default=0.8, ge=0.0, le=1.0)


# ─── Monolith ─────────────────────────────────────────────────────────────────

class MonolithModule(BaseModel):
    name: str
    responsibilities: list[str] = Field(default_factory=list)
    allowed_dependencies: list[str] = Field(default_factory=list)
    technology_hints: list[str] = Field(default_factory=list)


class MonolithSystemDesign(BaseModel):
    design_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str
    modules: list[MonolithModule]
    layering_strategy: MonolithLayering
    anti_corruption_layers: list[str] = Field(default_factory=list)
    deployment_strategy: str = ""
    shared_kernel: list[str] = Field(default_factory=list)
    rationale: str = ""
    design_confidence: float = Field(default=0.8, ge=0.0, le=1.0)


# ─── Union output ─────────────────────────────────────────────────────────────

class SystemDesignOutput(BaseModel):
    design_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str
    active_partner: str = ""
    microservices_design: MicroservicesSystemDesign | None = None
    hexagonal_design: HexagonalSystemDesign | None = None
    monolith_design: MonolithSystemDesign | None = None
