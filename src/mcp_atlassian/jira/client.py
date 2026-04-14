from __future__ import annotations

import base64
from typing import Any

import httpx

from .config import JiraConfig


class JiraClient:
    """JIRA REST API v3 클라이언트."""

    def __init__(self, config: JiraConfig) -> None:
        self._config = config
        credentials = base64.b64encode(
            f"{config.email}:{config.api_token}".encode()
        ).decode()
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """GET 요청."""
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, json_data: dict[str, Any] | None = None) -> dict:
        """POST 요청."""
        response = await self._client.post(path, json=json_data)
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()

    # ── JIRA API 메서드 ──

    async def get_issue(self, issue_key: str) -> dict:
        return await self.get(f"/rest/api/3/issue/{issue_key}")

    async def get_comments(self, issue_key: str) -> dict:
        return await self.get(f"/rest/api/3/issue/{issue_key}/comment")

    async def add_comment(self, issue_key: str, body: dict) -> dict:
        return await self.post(f"/rest/api/3/issue/{issue_key}/comment", json_data=body)

    async def search_issues(self, jql: str, max_results: int = 20) -> dict:
        return await self.get(
            "/rest/api/3/search",
            params={"jql": jql, "maxResults": max_results},
        )

    async def get_transitions(self, issue_key: str) -> dict:
        return await self.get(f"/rest/api/3/issue/{issue_key}/transitions")

    async def transition_issue(self, issue_key: str, transition_id: str) -> dict:
        return await self.post(
            f"/rest/api/3/issue/{issue_key}/transitions",
            json_data={"transition": {"id": transition_id}},
        )
