from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from .config import GitLabConfig


def _pid(project_id: str | int) -> str:
    """project_id가 `group/project` 같은 경로면 URL 인코딩, 숫자 ID면 그대로."""
    pid = str(project_id)
    if "/" in pid:
        return quote(pid, safe="")
    return pid


class GitLabClient:
    """GitLab REST API v4 클라이언트."""

    def __init__(self, config: GitLabConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=f"{config.base_url}/api/v4",
            headers={
                "PRIVATE-TOKEN": config.token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ── 저수준 HTTP ──

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def post(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = await self._client.post(path, json=json_data, params=params)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    async def put(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = await self._client.put(path, json=json_data, params=params)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    # ── Projects / Repository ──

    async def list_projects(
        self,
        search: str | None = None,
        membership: bool = True,
        per_page: int = 20,
    ) -> list[dict]:
        params: dict[str, Any] = {"membership": str(membership).lower(), "per_page": per_page}
        if search:
            params["search"] = search
        return await self.get("/projects", params=params)

    async def get_project(self, project_id: str | int) -> dict:
        return await self.get(f"/projects/{_pid(project_id)}")

    async def get_file_contents(
        self,
        project_id: str | int,
        file_path: str,
        ref: str = "HEAD",
    ) -> dict:
        encoded = quote(file_path, safe="")
        return await self.get(
            f"/projects/{_pid(project_id)}/repository/files/{encoded}",
            params={"ref": ref},
        )

    async def get_repository_tree(
        self,
        project_id: str | int,
        path: str = "",
        ref: str | None = None,
        recursive: bool = False,
        per_page: int = 100,
    ) -> list[dict]:
        params: dict[str, Any] = {"per_page": per_page}
        if path:
            params["path"] = path
        if ref:
            params["ref"] = ref
        if recursive:
            params["recursive"] = "true"
        return await self.get(f"/projects/{_pid(project_id)}/repository/tree", params=params)

    async def list_commits(
        self,
        project_id: str | int,
        ref_name: str | None = None,
        since: str | None = None,
        until: str | None = None,
        per_page: int = 20,
    ) -> list[dict]:
        params: dict[str, Any] = {"per_page": per_page}
        if ref_name:
            params["ref_name"] = ref_name
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        return await self.get(f"/projects/{_pid(project_id)}/repository/commits", params=params)

    # ── Branches ──

    async def list_branches(
        self,
        project_id: str | int,
        search: str | None = None,
        per_page: int = 50,
    ) -> list[dict]:
        params: dict[str, Any] = {"per_page": per_page}
        if search:
            params["search"] = search
        return await self.get(f"/projects/{_pid(project_id)}/repository/branches", params=params)

    async def create_branch(
        self,
        project_id: str | int,
        branch: str,
        ref: str,
    ) -> dict:
        return await self.post(
            f"/projects/{_pid(project_id)}/repository/branches",
            params={"branch": branch, "ref": ref},
        )

    async def get_branch_diffs(
        self,
        project_id: str | int,
        from_ref: str,
        to_ref: str,
        straight: bool = False,
    ) -> dict:
        return await self.get(
            f"/projects/{_pid(project_id)}/repository/compare",
            params={"from": from_ref, "to": to_ref, "straight": str(straight).lower()},
        )

    # ── Merge Requests ──

    async def list_merge_requests(
        self,
        project_id: str | int,
        state: str = "opened",
        source_branch: str | None = None,
        target_branch: str | None = None,
        search: str | None = None,
        per_page: int = 20,
    ) -> list[dict]:
        params: dict[str, Any] = {"state": state, "per_page": per_page}
        if source_branch:
            params["source_branch"] = source_branch
        if target_branch:
            params["target_branch"] = target_branch
        if search:
            params["search"] = search
        return await self.get(f"/projects/{_pid(project_id)}/merge_requests", params=params)

    async def get_merge_request(self, project_id: str | int, iid: int) -> dict:
        return await self.get(f"/projects/{_pid(project_id)}/merge_requests/{iid}")

    async def create_merge_request(
        self,
        project_id: str | int,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str = "",
        remove_source_branch: bool = False,
        draft: bool = False,
    ) -> dict:
        payload: dict[str, Any] = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
        }
        if description:
            payload["description"] = description
        if remove_source_branch:
            payload["remove_source_branch"] = True
        if draft:
            payload["draft"] = True
        return await self.post(f"/projects/{_pid(project_id)}/merge_requests", json_data=payload)

    async def get_merge_request_diffs(
        self,
        project_id: str | int,
        iid: int,
        page: int = 1,
        per_page: int = 20,
        unidiff: bool = False,
    ) -> list[dict]:
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if unidiff:
            params["unidiff"] = "true"
        return await self.get(
            f"/projects/{_pid(project_id)}/merge_requests/{iid}/diffs",
            params=params,
        )

    async def approve_merge_request(self, project_id: str | int, iid: int) -> dict:
        return await self.post(f"/projects/{_pid(project_id)}/merge_requests/{iid}/approve")

    async def merge_merge_request(
        self,
        project_id: str | int,
        iid: int,
        merge_commit_message: str | None = None,
        squash: bool = False,
        should_remove_source_branch: bool = False,
        merge_when_pipeline_succeeds: bool = False,
    ) -> dict:
        payload: dict[str, Any] = {
            "squash": squash,
            "should_remove_source_branch": should_remove_source_branch,
            "merge_when_pipeline_succeeds": merge_when_pipeline_succeeds,
        }
        if merge_commit_message:
            payload["merge_commit_message"] = merge_commit_message
        return await self.put(
            f"/projects/{_pid(project_id)}/merge_requests/{iid}/merge",
            json_data=payload,
        )

    # ── MR 리뷰: Notes / Discussions / Draft Notes ──

    async def create_note(self, project_id: str | int, iid: int, body: str) -> dict:
        return await self.post(
            f"/projects/{_pid(project_id)}/merge_requests/{iid}/notes",
            json_data={"body": body},
        )

    async def mr_discussions(
        self,
        project_id: str | int,
        iid: int,
        per_page: int = 50,
    ) -> list[dict]:
        return await self.get(
            f"/projects/{_pid(project_id)}/merge_requests/{iid}/discussions",
            params={"per_page": per_page},
        )

    async def create_merge_request_thread(
        self,
        project_id: str | int,
        iid: int,
        body: str,
        position: dict[str, Any] | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"body": body}
        if position:
            payload["position"] = position
        return await self.post(
            f"/projects/{_pid(project_id)}/merge_requests/{iid}/discussions",
            json_data=payload,
        )

    async def create_draft_note(
        self,
        project_id: str | int,
        iid: int,
        body: str,
        position: dict[str, Any] | None = None,
        in_reply_to_discussion_id: str | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"note": body}
        if position:
            payload["position"] = position
        if in_reply_to_discussion_id:
            payload["in_reply_to_discussion_id"] = in_reply_to_discussion_id
        return await self.post(
            f"/projects/{_pid(project_id)}/merge_requests/{iid}/draft_notes",
            json_data=payload,
        )

    async def bulk_publish_draft_notes(self, project_id: str | int, iid: int) -> dict:
        return await self.post(
            f"/projects/{_pid(project_id)}/merge_requests/{iid}/draft_notes/bulk_publish"
        )