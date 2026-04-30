from __future__ import annotations

from typing import Any

import httpx

from .config import GitHubConfig


class GitHubClient:
    """GitHub REST API 클라이언트."""

    def __init__(self, config: GitHubConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
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

    async def post(self, path: str, json_data: dict[str, Any] | None = None) -> Any:
        response = await self._client.post(path, json=json_data)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    async def put(self, path: str, json_data: dict[str, Any] | None = None) -> Any:
        response = await self._client.put(path, json=json_data)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    # ── Repositories ──

    async def list_repos(
        self,
        search: str | None = None,
        per_page: int = 20,
    ) -> list[dict]:
        if search:
            data = await self.get("/search/repositories", params={"q": search, "per_page": per_page})
            return data.get("items", [])
        return await self.get("/user/repos", params={"per_page": per_page, "type": "all", "sort": "updated"})

    async def get_repo(self, owner_repo: str) -> dict:
        return await self.get(f"/repos/{owner_repo}")

    async def get_file_contents(
        self,
        owner_repo: str,
        file_path: str,
        ref: str = "HEAD",
    ) -> dict:
        params: dict[str, Any] = {}
        if ref and ref != "HEAD":
            params["ref"] = ref
        return await self.get(f"/repos/{owner_repo}/contents/{file_path.lstrip('/')}", params=params or None)

    async def get_repository_tree(
        self,
        owner_repo: str,
        path: str = "",
        ref: str = "HEAD",
        per_page: int = 100,
    ) -> list[dict]:
        """디렉토리 목록 조회 (GitHub Contents API 사용)."""
        params: dict[str, Any] = {}
        if ref and ref != "HEAD":
            params["ref"] = ref
        target = f"/repos/{owner_repo}/contents/{path.lstrip('/')}" if path else f"/repos/{owner_repo}/contents"
        result = await self.get(target, params=params or None)
        if isinstance(result, list):
            return result[:per_page]
        return [result]

    async def list_commits(
        self,
        owner_repo: str,
        sha: str | None = None,
        since: str | None = None,
        until: str | None = None,
        per_page: int = 20,
    ) -> list[dict]:
        params: dict[str, Any] = {"per_page": per_page}
        if sha:
            params["sha"] = sha
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        return await self.get(f"/repos/{owner_repo}/commits", params=params)

    # ── Branches ──

    async def list_branches(
        self,
        owner_repo: str,
        per_page: int = 50,
    ) -> list[dict]:
        return await self.get(f"/repos/{owner_repo}/branches", params={"per_page": per_page})

    async def create_branch(
        self,
        owner_repo: str,
        branch: str,
        sha: str,
    ) -> dict:
        return await self.post(
            f"/repos/{owner_repo}/git/refs",
            json_data={"ref": f"refs/heads/{branch}", "sha": sha},
        )

    async def compare(
        self,
        owner_repo: str,
        base: str,
        head: str,
    ) -> dict:
        return await self.get(f"/repos/{owner_repo}/compare/{base}...{head}")

    # ── Pull Requests ──

    async def list_pull_requests(
        self,
        owner_repo: str,
        state: str = "open",
        head: str | None = None,
        base: str | None = None,
        per_page: int = 20,
    ) -> list[dict]:
        params: dict[str, Any] = {"state": state, "per_page": per_page}
        if head:
            params["head"] = head
        if base:
            params["base"] = base
        return await self.get(f"/repos/{owner_repo}/pulls", params=params)

    async def get_pull_request(self, owner_repo: str, pull_number: int) -> dict:
        return await self.get(f"/repos/{owner_repo}/pulls/{pull_number}")

    async def create_pull_request(
        self,
        owner_repo: str,
        head: str,
        base: str,
        title: str,
        body: str = "",
        draft: bool = False,
    ) -> dict:
        payload: dict[str, Any] = {"head": head, "base": base, "title": title}
        if body:
            payload["body"] = body
        if draft:
            payload["draft"] = True
        return await self.post(f"/repos/{owner_repo}/pulls", json_data=payload)

    async def get_pull_request_files(
        self,
        owner_repo: str,
        pull_number: int,
        per_page: int = 100,
    ) -> list[dict]:
        return await self.get(
            f"/repos/{owner_repo}/pulls/{pull_number}/files",
            params={"per_page": per_page},
        )

    async def merge_pull_request(
        self,
        owner_repo: str,
        pull_number: int,
        commit_title: str | None = None,
        commit_message: str | None = None,
        merge_method: str = "merge",
    ) -> dict:
        payload: dict[str, Any] = {"merge_method": merge_method}
        if commit_title:
            payload["commit_title"] = commit_title
        if commit_message:
            payload["commit_message"] = commit_message
        return await self.put(f"/repos/{owner_repo}/pulls/{pull_number}/merge", json_data=payload)

    # ── PR 리뷰 / 댓글 ──

    async def list_reviews(self, owner_repo: str, pull_number: int) -> list[dict]:
        return await self.get(f"/repos/{owner_repo}/pulls/{pull_number}/reviews")

    async def create_review(
        self,
        owner_repo: str,
        pull_number: int,
        event: str,
        body: str = "",
        comments: list[dict] | None = None,
    ) -> dict:
        """event: APPROVE | REQUEST_CHANGES | COMMENT | PENDING"""
        payload: dict[str, Any] = {"event": event}
        if body:
            payload["body"] = body
        if comments:
            payload["comments"] = comments
        return await self.post(f"/repos/{owner_repo}/pulls/{pull_number}/reviews", json_data=payload)

    async def list_review_comments(
        self,
        owner_repo: str,
        pull_number: int,
        per_page: int = 50,
    ) -> list[dict]:
        return await self.get(
            f"/repos/{owner_repo}/pulls/{pull_number}/comments",
            params={"per_page": per_page},
        )

    async def create_review_comment(
        self,
        owner_repo: str,
        pull_number: int,
        body: str,
        commit_id: str,
        path: str,
        line: int,
        side: str = "RIGHT",
    ) -> dict:
        return await self.post(
            f"/repos/{owner_repo}/pulls/{pull_number}/comments",
            json_data={
                "body": body,
                "commit_id": commit_id,
                "path": path,
                "line": line,
                "side": side,
            },
        )

    async def create_issue_comment(
        self,
        owner_repo: str,
        issue_number: int,
        body: str,
    ) -> dict:
        return await self.post(
            f"/repos/{owner_repo}/issues/{issue_number}/comments",
            json_data={"body": body},
        )

    async def get_issue_comments(
        self,
        owner_repo: str,
        issue_number: int,
        per_page: int = 50,
    ) -> list[dict]:
        return await self.get(
            f"/repos/{owner_repo}/issues/{issue_number}/comments",
            params={"per_page": per_page},
        )

    # ── 파일 커밋 ──

    def _author_payload(self) -> dict[str, str] | None:
        """config에 author 정보가 있으면 author 딕셔너리를 반환한다."""
        if self._config.author_name and self._config.author_email:
            return {"name": self._config.author_name, "email": self._config.author_email}
        return None

    async def create_or_update_file(
        self,
        owner_repo: str,
        file_path: str,
        message: str,
        content_bytes: bytes,
        branch: str | None = None,
        sha: str | None = None,
    ) -> dict:
        """파일을 생성하거나 업데이트하는 커밋을 만든다.

        sha가 있으면 기존 파일 업데이트, 없으면 새 파일 생성.
        """
        import base64
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content_bytes).decode(),
        }
        if branch:
            payload["branch"] = branch
        if sha:
            payload["sha"] = sha
        author = self._author_payload()
        if author:
            payload["author"] = author
            payload["committer"] = author
        return await self.put(f"/repos/{owner_repo}/contents/{file_path.lstrip('/')}", json_data=payload)

    async def get_file_sha(self, owner_repo: str, file_path: str, ref: str | None = None) -> str | None:
        """파일의 현재 SHA를 반환한다. 파일이 없으면 None."""
        try:
            params: dict[str, Any] = {}
            if ref:
                params["ref"] = ref
            data = await self.get(
                f"/repos/{owner_repo}/contents/{file_path.lstrip('/')}",
                params=params or None,
            )
            return data.get("sha")
        except Exception:
            return None