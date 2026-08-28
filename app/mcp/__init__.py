import logging

from .bootstrap import create_architecture_registry, default_architecture_agents
from .registry import (
    AgentRegistry,
    DuplicateAgentError,
    RegistryError,
    UnknownAgentError,
)

logger = logging.getLogger(__name__)

try:
    from .backend_mcp import BackendMCPServer
    from .frontend_mcp import FrontendMCPServer
    from .orchestrator_mcp import OrchestratorMCPServer
except ImportError as _exc:
    logger.warning("MCP server modules unavailable (%s); registry subsystem only.", _exc)
    BackendMCPServer = None
    FrontendMCPServer = None
    OrchestratorMCPServer = None

__all__ = [
    "BackendMCPServer",
    "FrontendMCPServer",
    "OrchestratorMCPServer",
    "AgentRegistry",
    "DuplicateAgentError",
    "RegistryError",
    "UnknownAgentError",
    "create_architecture_registry",
    "default_architecture_agents",
]
