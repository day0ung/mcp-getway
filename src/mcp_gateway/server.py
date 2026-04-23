"""FastMCP 서버 인스턴스."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .confluence.client import ConfluenceClient
from .confluence.config import ConfluenceConfig
from .gitlab.client import GitLabClient
from .gitlab.config import GitLabConfig
from .jira.client import JiraClient
from .jira.config import JiraConfig
from .tools.confluence import register_tools as register_confluence_tools
from .tools.gitlab import register_tools as register_gitlab_tools
from .tools.jira import register_tools as register_jira_tools


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """서버 시작/종료 시 Jira/Confluence/GitLab 클라이언트를 관리한다."""
    jira_config = JiraConfig.from_env()
    confluence_config = ConfluenceConfig.from_env()
    gitlab_config = GitLabConfig.from_env()
    jira_client = JiraClient(jira_config)
    confluence_client = ConfluenceClient(confluence_config)
    gitlab_client = GitLabClient(gitlab_config)
    try:
        yield {
            "jira_client": jira_client,
            "confluence_client": confluence_client,
            "gitlab_client": gitlab_client,
        }
    finally:
        await jira_client.close()
        await confluence_client.close()
        await gitlab_client.close()


def create_mcp(host: str = "0.0.0.0", port: int = 8000) -> FastMCP:
    """FastMCP 인스턴스를 생성한다."""
    mcp = FastMCP(
        "MCP Gateway",
        lifespan=lifespan,
        host=host,
        port=port,
    )
    register_jira_tools(mcp)
    register_confluence_tools(mcp)
    register_gitlab_tools(mcp)
    return mcp