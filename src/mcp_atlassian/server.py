"""FastMCP 서버 인스턴스."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .jira.client import JiraClient
from .jira.config import JiraConfig
from .tools.jira import register_tools


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """서버 시작/종료 시 JiraClient를 관리한다."""
    config = JiraConfig.from_env()
    client = JiraClient(config)
    try:
        yield {"jira_client": client}
    finally:
        await client.close()


def create_mcp(host: str = "0.0.0.0", port: int = 8000) -> FastMCP:
    """FastMCP 인스턴스를 생성한다."""
    mcp = FastMCP(
        "JIRA MCP Server",
        lifespan=lifespan,
        host=host,
        port=port,
    )
    register_tools(mcp)
    return mcp
