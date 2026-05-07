from __future__ import annotations

import base64
from typing import Any

import httpx

from .config import ConfluenceConfig


class ConfluenceClient:
    """Confluence Cloud REST API 클라이언트.

    페이지 조회/생성/수정/삭제는 v2 API를 사용한다.
    검색은 v1 CQL API를 사용한다 (v2에는 아직 대체가 없다).
    """

    def __init__(self, config: ConfluenceConfig) -> None:
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
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, json_data: dict[str, Any] | None = None) -> dict:
        response = await self._client.post(path, json=json_data)
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()

    async def put(self, path: str, json_data: dict[str, Any] | None = None) -> dict:
        response = await self._client.put(path, json=json_data)
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()

    async def delete(self, path: str) -> None:
        response = await self._client.delete(path)
        response.raise_for_status()

    # ── Confluence API 메서드 ──

    async def get_page(self, page_id: str, body_format: str = "storage") -> dict:
        """페이지 상세 + 본문 조회."""
        return await self.get(
            f"/wiki/api/v2/pages/{page_id}",
            params={"body-format": body_format},
        )

    async def search(self, cql: str, limit: int = 20) -> dict:
        """CQL로 콘텐츠 검색."""
        return await self.get(
            "/wiki/rest/api/search",
            params={"cql": cql, "limit": limit},
        )

    async def get_space_by_key(self, space_key: str) -> dict | None:
        """space key로 스페이스 정보를 조회한다. 없으면 None."""
        raw = await self.get(
            "/wiki/api/v2/spaces",
            params={"keys": space_key, "limit": 1},
        )
        results = raw.get("results", [])
        return results[0] if results else None

    async def create_page(
        self,
        space_id: str,
        title: str,
        body_value: str,
        body_representation: str = "storage",
        parent_id: str | None = None,
    ) -> dict:
        """페이지 생성."""
        payload: dict[str, Any] = {
            "spaceId": space_id,
            "status": "current",
            "title": title,
            "body": {
                "representation": body_representation,
                "value": body_value,
            },
        }
        if parent_id:
            payload["parentId"] = parent_id
        return await self.post("/wiki/api/v2/pages", json_data=payload)

    async def update_page(
        self,
        page_id: str,
        title: str,
        body_value: str,
        version_number: int,
        body_representation: str = "storage",
    ) -> dict:
        """페이지 수정. version_number는 현재 버전 + 1 이어야 한다."""
        payload = {
            "id": page_id,
            "status": "current",
            "title": title,
            "body": {
                "representation": body_representation,
                "value": body_value,
            },
            "version": {"number": version_number},
        }
        return await self.put(f"/wiki/api/v2/pages/{page_id}", json_data=payload)

    async def delete_page(self, page_id: str) -> None:
        await self.delete(f"/wiki/api/v2/pages/{page_id}")

    async def get_database(self, database_id: str, body_format: str = "storage") -> dict:
        """데이터베이스 메타데이터 조회."""
        return await self.get(
            f"/wiki/api/v2/databases/{database_id}",
            params={"body-format": body_format},
        )

    async def list_databases(
        self, space_key: str | None = None, limit: int = 25
    ) -> dict:
        """데이터베이스 목록 조회. CQL을 사용 (v2 목록 API는 서버 측 500 오류).

        space_key를 주면 해당 스페이스로 필터링 (예: DEV, ~71202050cf...).
        """
        cql = "type=database"
        if space_key:
            cql += f' AND space="{space_key}"'
        return await self.get("/wiki/rest/api/search", params={"cql": cql, "limit": limit})