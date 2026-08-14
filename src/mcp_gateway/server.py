"""FastMCP 서버 인스턴스."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .confluence.client import ConfluenceClient
from .confluence.config import ConfluenceConfig
from .github.client import GitHubClient
from .github.config import GitHubConfig
from .gitlab.client import GitLabClient
from .gitlab.config import GitLabConfig
from .jira.client import JiraClient
from .jira.config import JiraConfig
from .notion.client import NotionClient
from .notion.config import NotionConfig
from .postgres.client import PostgresClient
from .postgres.config import PostgresConfig
from .tools.confluence import register_tools as register_confluence_tools
from .tools.github import register_tools as register_github_tools
from .tools.gitlab import register_tools as register_gitlab_tools
from .tools.jira import register_tools as register_jira_tools
from .tools.notion import register_tools as register_notion_tools
from .tools.postgres import register_tools as register_postgres_tools


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """서버 시작/종료 시 Jira/Confluence/GitLab/Notion/GitHub 클라이언트를 관리한다."""
    jira_config = JiraConfig.from_env()
    confluence_config = ConfluenceConfig.from_env()
    gitlab_config = GitLabConfig.from_env()
    notion_config = NotionConfig.from_env()
    github_config = GitHubConfig.from_env()
    postgres_config = PostgresConfig.from_env()
    jira_client = JiraClient(jira_config)
    confluence_client = ConfluenceClient(confluence_config)
    gitlab_client = GitLabClient(gitlab_config)
    notion_client = NotionClient(notion_config)
    github_client = GitHubClient(github_config)
    postgres_clients = {
        name: PostgresClient(conn_config)
        for name, conn_config in postgres_config.connections.items()
    }
    try:
        yield {
            "jira_client": jira_client,
            "confluence_client": confluence_client,
            "gitlab_client": gitlab_client,
            "notion_client": notion_client,
            "github_client": github_client,
            "postgres_clients": postgres_clients,
        }
    finally:
        await jira_client.close()
        await confluence_client.close()
        await gitlab_client.close()
        await notion_client.close()
        await github_client.close()
        for postgres_client in postgres_clients.values():
            await postgres_client.close()


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
    register_notion_tools(mcp)
    register_github_tools(mcp)
    register_postgres_tools(mcp)
    return mcp