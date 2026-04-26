from __future__ import annotations

import re
from typing import Any

import httpx

from .config import NotionConfig


_UUID_RE = re.compile(
    r"([0-9a-fA-F]{8})([0-9a-fA-F]{4})([0-9a-fA-F]{4})([0-9a-fA-F]{4})([0-9a-fA-F]{12})"
)


def normalize_id(raw: str) -> str:
    """Notion ID를 dash 포함 UUID 포맷으로 정규화한다.

    URL이 통째로 들어오거나 dash 없는 32자가 와도 처리한다.
    """
    if not raw:
        return raw
    cleaned = raw.strip().split("?")[0].rstrip("/")
    if "/" in cleaned:
        cleaned = cleaned.rsplit("/", 1)[-1]
    if "-" in cleaned and len(cleaned) > 32:
        cleaned = cleaned.rsplit("-", 1)[-1]
    cleaned = cleaned.replace("-", "")
    if len(cleaned) != 32:
        return raw
    return _UUID_RE.sub(r"\1-\2-\3-\4-\5", cleaned)


class NotionClient:
    """Notion REST API 클라이언트."""

    def __init__(self, config: NotionConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.token}",
                "Notion-Version": config.version,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, json_data: dict[str, Any] | None = None) -> dict:
        response = await self._client.post(path, json=json_data or {})
        response.raise_for_status()
        return response.json()

    async def patch(self, path: str, json_data: dict[str, Any] | None = None) -> dict:
        response = await self._client.patch(path, json=json_data or {})
        response.raise_for_status()
        return response.json()

    # ── Notion API 메서드 ──

    async def search(
        self,
        query: str = "",
        filter_type: str | None = None,
        page_size: int = 20,
    ) -> dict:
        """워크스페이스 내 페이지/데이터베이스 검색.

        filter_type: "page" | "database" (None이면 전체)
        """
        payload: dict[str, Any] = {"query": query, "page_size": page_size}
        if filter_type:
            payload["filter"] = {"property": "object", "value": filter_type}
        return await self.post("/v1/search", json_data=payload)

    async def get_page(self, page_id: str) -> dict:
        """페이지 properties 조회 (본문 블록은 별도 API)."""
        return await self.get(f"/v1/pages/{normalize_id(page_id)}")

    async def get_block_children(
        self,
        block_id: str,
        start_cursor: str | None = None,
        page_size: int = 100,
    ) -> dict:
        """블록 자식 조회 (페이지 본문 = 페이지 ID의 자식 블록)."""
        params: dict[str, Any] = {"page_size": page_size}
        if start_cursor:
            params["start_cursor"] = start_cursor
        return await self.get(
            f"/v1/blocks/{normalize_id(block_id)}/children",
            params=params,
        )

    async def get_all_block_children(self, block_id: str) -> list[dict]:
        """페이지네이션 풀어서 모든 자식 블록 수집."""
        results: list[dict] = []
        cursor: str | None = None
        while True:
            resp = await self.get_block_children(block_id, start_cursor=cursor)
            results.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
            if not cursor:
                break
        return results

    async def create_page(
        self,
        parent: dict[str, Any],
        properties: dict[str, Any],
        children: list[dict] | None = None,
    ) -> dict:
        """페이지 생성.

        parent 예시:
            {"page_id": "..."}     # 페이지 하위
            {"database_id": "..."} # 데이터베이스 row
        """
        payload: dict[str, Any] = {"parent": parent, "properties": properties}
        if children:
            payload["children"] = children
        return await self.post("/v1/pages", json_data=payload)

    async def update_page(
        self,
        page_id: str,
        properties: dict[str, Any] | None = None,
        archived: bool | None = None,
    ) -> dict:
        """페이지 properties 수정 또는 archive 토글."""
        payload: dict[str, Any] = {}
        if properties is not None:
            payload["properties"] = properties
        if archived is not None:
            payload["archived"] = archived
        return await self.patch(
            f"/v1/pages/{normalize_id(page_id)}",
            json_data=payload,
        )

    async def append_blocks(
        self,
        block_id: str,
        children: list[dict],
    ) -> dict:
        """블록(또는 페이지) 하위에 블록 추가."""
        return await self.patch(
            f"/v1/blocks/{normalize_id(block_id)}/children",
            json_data={"children": children},
        )

    async def get_database(self, database_id: str) -> dict:
        """데이터베이스 메타데이터 + 스키마 조회."""
        return await self.get(f"/v1/databases/{normalize_id(database_id)}")

    async def query_database(
        self,
        database_id: str,
        filter_: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        page_size: int = 20,
        start_cursor: str | None = None,
    ) -> dict:
        """데이터베이스 row 조회 (filter/sort 지원)."""
        payload: dict[str, Any] = {"page_size": page_size}
        if filter_:
            payload["filter"] = filter_
        if sorts:
            payload["sorts"] = sorts
        if start_cursor:
            payload["start_cursor"] = start_cursor
        return await self.post(
            f"/v1/databases/{normalize_id(database_id)}/query",
            json_data=payload,
        )