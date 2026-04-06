"""Claude Code SDK adapter: wraps shared ToolDefs as MCP tools."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from claude_code_sdk import SdkMcpTool, create_sdk_mcp_server

from ._tools import ToolDef, get_tools

if TYPE_CHECKING:
    from claude_code_sdk.types import McpSdkServerConfig

logger = logging.getLogger(__name__)


def _to_json_schema(params: dict[str, Any]) -> dict[str, Any]:
    """Convert a ToolDef.parameters to a JSON Schema dict."""
    if "type" in params and "properties" in params:
        return params  # already a full schema (e.g. MDA_SCHEMA)
    if not params:
        return {"type": "object", "properties": {}}
    # Simple {name: type} mapping
    properties = {}
    for name, ptype in params.items():
        if ptype is str:
            properties[name] = {"type": "string"}
        elif ptype is int:
            properties[name] = {"type": "integer"}
        elif ptype is float:
            properties[name] = {"type": "number"}
        elif ptype is bool:
            properties[name] = {"type": "boolean"}
        else:
            properties[name] = {"type": "string"}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
    }


def _tooldef_to_mcp(td: ToolDef) -> SdkMcpTool[Any]:
    """Wrap a ToolDef as a claude-code-sdk SdkMcpTool."""
    schema = _to_json_schema(td.parameters)

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        logger.debug("Tool CALL: %s  args=%s", td.name, args)
        try:
            # Run the sync handler in a thread to avoid blocking asyncio
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, td.handler, args)
            logger.debug("Tool OK: %s  len=%d", td.name, len(text))
        except Exception:
            logger.exception("Tool ERROR: %s", td.name)
            raise
        return {"content": [{"type": "text", "text": text}]}

    return SdkMcpTool(
        name=td.name,
        description=td.description,
        input_schema=schema,
        handler=handler,
    )


def create_microscope_server(*, hardware_enabled: bool = True) -> McpSdkServerConfig:
    """Create an in-process MCP server with the appropriate tool set."""
    tools = get_tools(hardware_enabled=hardware_enabled)
    mcp_tools = [_tooldef_to_mcp(td) for td in tools]
    logger.debug(
        "Creating MCP server (hardware=%s) with %d tools: %s",
        hardware_enabled,
        len(mcp_tools),
        [t.name for t in mcp_tools],
    )
    return create_sdk_mcp_server("microscope", tools=mcp_tools)
