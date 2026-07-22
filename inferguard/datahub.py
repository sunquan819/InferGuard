from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from .models import Evidence, Incident, utc_now


class DataHubContextProvider(Protocol):
    """Boundary used by the context agent for fixture and live MCP modes."""

    def collect(self, incident: Incident) -> list[Evidence]: ...


@dataclass(slots=True)
class ScenarioDataHubContextProvider:
    """Deterministic DataHub MCP responses embedded in a replay scenario."""

    scenario: dict[str, Any]

    def collect(self, incident: Incident) -> list[Evidence]:
        context = self.scenario.get("datahub_context", {})
        evidence: list[Evidence] = []
        for index, item in enumerate(context.get("evidence", []), start=1):
            evidence.append(
                Evidence(
                    evidence_id=f"DH-{index:03d}",
                    kind=item["kind"],
                    source=f"datahub-mcp/{item['tool']}",
                    observed_at=item.get("observed_at", utc_now()),
                    summary=item["summary"],
                    data={
                        "mcp_tool": item["tool"],
                        "arguments": item.get("arguments", {}),
                        "result": item.get("result", {}),
                        "mode": "fixture",
                    },
                )
            )
        return evidence


@dataclass(slots=True)
class MCPDataHubContextProvider:
    """Live adapter for the official self-hosted DataHub MCP server."""

    scenario: dict[str, Any]
    command: str = "uvx"
    package: str = "mcp-server-datahub@latest"

    def collect(self, incident: Incident) -> list[Evidence]:
        return asyncio.run(self._collect(incident))

    async def _collect(self, incident: Incident) -> list[Evidence]:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError(
                'live DataHub mode requires: pip install -e ".[datahub]"'
            ) from exc

        config = self.scenario.get("datahub_context", {})
        primary_urn = config.get("primary_urn")
        query = config.get("query", incident.service)
        if not primary_urn:
            raise ValueError("live DataHub mode requires datahub_context.primary_urn")

        environment = os.environ.copy()
        if not environment.get("DATAHUB_GMS_URL"):
            raise RuntimeError("DATAHUB_GMS_URL is required for live DataHub mode")

        parameters = StdioServerParameters(
            command=self.command,
            args=[self.package],
            env=environment,
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                available = {
                    tool.name: tool for tool in (await session.list_tools()).tools
                }
                requested_calls = [
                    ("search", {"query": query}),
                    ("get_entities", {"urns": [primary_urn]}),
                    (
                        "get_lineage",
                        {"urn": primary_urn, "direction": "upstream", "max_hops": 3},
                    ),
                    (
                        "get_lineage",
                        {"urn": primary_urn, "direction": "downstream", "max_hops": 3},
                    ),
                ]
                evidence: list[Evidence] = []
                for index, (name, candidates) in enumerate(requested_calls, start=1):
                    if name not in available:
                        raise RuntimeError(f"DataHub MCP tool is unavailable: {name}")
                    arguments = _supported_arguments(
                        available[name].inputSchema, candidates
                    )
                    result = await session.call_tool(name, arguments=arguments)
                    if getattr(result, "isError", False):
                        raise RuntimeError(
                            f"DataHub MCP tool returned an error: {name}"
                        )
                    payload = _result_payload(result)
                    evidence.append(
                        Evidence(
                            evidence_id=f"DH-{index:03d}",
                            kind=f"datahub_{name}",
                            source=f"datahub-mcp/{name}",
                            observed_at=utc_now(),
                            summary=_summary(name, candidates),
                            data={
                                "mcp_tool": name,
                                "arguments": arguments,
                                "result": payload,
                                "mode": "live",
                            },
                        )
                    )
                return evidence


def _supported_arguments(
    input_schema: dict[str, Any], candidates: dict[str, Any]
) -> dict[str, Any]:
    """Pass only arguments advertised by the connected MCP server version."""

    properties = input_schema.get("properties", {})
    aliases = {
        "urn": ("urn", "source_urn", "entity_urn"),
        "urns": ("urns", "entity_urns"),
        "max_hops": ("max_hops", "maxHops", "degree"),
    }
    supported: dict[str, Any] = {}
    for canonical, value in candidates.items():
        names = aliases.get(canonical, (canonical,))
        target = next((name for name in names if name in properties), None)
        if target is not None:
            supported[target] = value
    required = set(input_schema.get("required", []))
    missing = required.difference(supported)
    if missing:
        raise RuntimeError(
            "unsupported DataHub MCP tool schema; missing arguments: "
            + ", ".join(sorted(missing))
        )
    return supported


def _result_payload(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if structured is not None:
        return _json_safe(structured)

    items: list[Any] = []
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if text is None:
            items.append(str(item))
            continue
        try:
            items.append(json.loads(text))
        except json.JSONDecodeError:
            items.append(text)
    if len(items) == 1:
        return _json_safe(items[0])
    return _json_safe(items)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(by_alias=True))
    return str(value)


def _summary(tool: str, arguments: dict[str, Any]) -> str:
    if tool == "search":
        return f"DataHub search resolved assets related to {arguments['query']}"
    if tool == "get_entities":
        return "DataHub returned metadata, ownership, schema, and health context"
    return (
        "DataHub traced "
        f"{arguments['direction']} impact for the primary incident asset"
    )
