"""Confluence MCP 도구 정의."""

from __future__ import annotations

import json
import logging
from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from ..confluence.models import ConfluenceDatabase, ConfluencePage, ConfluenceSearchHit

logger = logging.getLogger("mcp_gateway.tools.confluence")


def register_tools(mcp: FastMCP) -> None:
    """MCP 서버에 Confluence 도구들을 등록한다."""

    @mcp.tool()
    async def get_confluence_page(
        ctx: Context,
        page_id: Annotated[str, Field(description="Confluence 페이지 ID (숫자)")],
        body_format: Annotated[
            str,
            Field(
                description="본문 포맷: storage(XHTML) | atlas_doc_format(ADF)",
                default="storage",
            ),
        ] = "storage",
    ) -> str:
        """Confluence 페이지 본문과 메타데이터를 조회한다."""
        logger.info("get_confluence_page 호출: %s (format=%s)", page_id, body_format)
        client = ctx.request_context.lifespan_context["confluence_client"]
        raw = await client.get_page(page_id, body_format=body_format)
        page = ConfluencePage.from_raw(raw)
        logger.info("get_confluence_page 완료: %s", page_id)
        return json.dumps(page, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def search_confluence(
        ctx: Context,
        cql: Annotated[
            str,
            Field(
                description='CQL 쿼리 (예: space=DEV AND text ~ "로그인" AND type=page)',
            ),
        ],
        limit: Annotated[int, Field(description="최대 결과 수", default=20)] = 20,
    ) -> str:
        """CQL로 Confluence 콘텐츠를 검색한다."""
        logger.info("search_confluence 호출: cql=%s, limit=%d", cql, limit)
        client = ctx.request_context.lifespan_context["confluence_client"]
        raw = await client.search(cql, limit=limit)
        hits = [ConfluenceSearchHit.from_raw(r) for r in raw.get("results", [])]
        result = {
            "total_size": raw.get("totalSize", len(hits)),
            "results": hits,
        }
        logger.info("search_confluence 완료: %d건", len(hits))
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def create_confluence_page(
        ctx: Context,
        space_key: Annotated[str, Field(description="스페이스 키 (예: DEV)")],
        title: Annotated[str, Field(description="페이지 제목")],
        body: Annotated[
            str,
            Field(
                description=(
                    "페이지 본문. body_representation에 맞는 포맷으로 전달. "
                    "storage면 XHTML (예: <p>hello</p>)"
                ),
            ),
        ],
        body_representation: Annotated[
            str,
            Field(description="본문 포맷: storage | atlas_doc_format", default="storage"),
        ] = "storage",
        parent_id: Annotated[
            str,
            Field(description="부모 페이지 ID (선택)", default=""),
        ] = "",
    ) -> str:
        """Confluence 페이지를 생성한다."""
        logger.info("create_confluence_page 호출: space=%s, title=%s", space_key, title)
        client = ctx.request_context.lifespan_context["confluence_client"]
        space = await client.get_space_by_key(space_key)
        if not space:
            return json.dumps(
                {"success": False, "error": f"스페이스를 찾을 수 없음: {space_key}"},
                ensure_ascii=False,
            )
        raw = await client.create_page(
            space_id=space["id"],
            title=title,
            body_value=body,
            body_representation=body_representation,
            parent_id=parent_id or None,
        )
        page = ConfluencePage.from_raw(raw)
        logger.info("create_confluence_page 완료: id=%s", page.get("id", ""))
        return json.dumps(page, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def update_confluence_page(
        ctx: Context,
        page_id: Annotated[str, Field(description="수정할 페이지 ID")],
        title: Annotated[
            str,
            Field(description="페이지 제목. 비우면 기존 제목 유지", default=""),
        ] = "",
        body: Annotated[
            str,
            Field(
                description="새 본문 (body_representation 포맷). 비우면 기존 본문 유지",
                default="",
            ),
        ] = "",
        body_representation: Annotated[
            str,
            Field(description="본문 포맷: storage | atlas_doc_format", default="storage"),
        ] = "storage",
    ) -> str:
        """Confluence 페이지를 수정한다.

        Confluence는 PUT 시 제목/본문/버전을 모두 전달해야 하므로
        기존 페이지를 먼저 조회해 빈 파라미터를 채우고 version을 +1 한다.
        """
        logger.info("update_confluence_page 호출: %s", page_id)
        client = ctx.request_context.lifespan_context["confluence_client"]
        current = await client.get_page(page_id, body_format=body_representation)
        current_body = (current.get("body") or {}).get(body_representation) or {}
        new_title = title or current.get("title", "")
        new_body = body or current_body.get("value", "")
        current_version = (current.get("version") or {}).get("number", 1)
        next_version = int(current_version) + 1

        raw = await client.update_page(
            page_id=page_id,
            title=new_title,
            body_value=new_body,
            version_number=next_version,
            body_representation=body_representation,
        )
        page = ConfluencePage.from_raw(raw)
        logger.info(
            "update_confluence_page 완료: %s (v%d → v%d)",
            page_id,
            current_version,
            next_version,
        )
        return json.dumps(page, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def get_confluence_database(
        ctx: Context,
        database_id: Annotated[str, Field(description="Confluence 데이터베이스 ID (숫자)")],
    ) -> str:
        """Confluence 데이터베이스 메타데이터를 조회한다.

        데이터베이스 URL 예시:
        https://<host>/wiki/spaces/<space>/database/<id>
        위 URL의 마지막 숫자 부분이 database_id 이다.
        """
        logger.info("get_confluence_database 호출: %s", database_id)
        client = ctx.request_context.lifespan_context["confluence_client"]
        raw = await client.get_database(database_id)
        db = ConfluenceDatabase.from_raw(raw)
        logger.info("get_confluence_database 완료: %s", database_id)
        return json.dumps(db, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def list_confluence_databases(
        ctx: Context,
        space_key: Annotated[
            str,
            Field(
                description="스페이스 키로 필터링 (선택). 예: DEV, ~71202050cf... — 비우면 전체 조회",
                default="",
            ),
        ] = "",
        limit: Annotated[int, Field(description="최대 결과 수", default=25)] = 25,
    ) -> str:
        """Confluence 데이터베이스 목록을 조회한다."""
        logger.info("list_confluence_databases 호출: space_key=%s, limit=%d", space_key, limit)
        client = ctx.request_context.lifespan_context["confluence_client"]
        raw = await client.list_databases(space_key=space_key or None, limit=limit)
        hits = raw.get("results", [])
        dbs = [ConfluenceDatabase.from_raw(h.get("content", h)) for h in hits]
        result = {
            "total_size": raw.get("totalSize", len(dbs)),
            "results": dbs,
        }
        logger.info("list_confluence_databases 완료: %d건", len(dbs))
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def delete_confluence_page(
        ctx: Context,
        page_id: Annotated[str, Field(description="삭제할 페이지 ID")],
    ) -> str:
        """Confluence 페이지를 삭제한다 (휴지통으로 이동)."""
        logger.info("delete_confluence_page 호출: %s", page_id)
        client = ctx.request_context.lifespan_context["confluence_client"]
        await client.delete_page(page_id)
        logger.info("delete_confluence_page 완료: %s", page_id)
        return json.dumps(
            {"success": True, "page_id": page_id},
            ensure_ascii=False,
        )