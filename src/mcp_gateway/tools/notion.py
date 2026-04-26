"""Notion MCP 도구 정의."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from ..notion.models import NotionBlock, NotionDatabase, NotionPage, NotionSearchHit

logger = logging.getLogger("mcp_gateway.tools.notion")


def _parse_json_arg(raw: str, field: str) -> Any:
    """JSON 문자열 파라미터를 파싱한다. 빈 문자열이면 None."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field} JSON 파싱 실패: {exc.msg}") from exc


def _text_to_rich_text(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text}}]


def _markdown_lines_to_blocks(text: str) -> list[dict[str, Any]]:
    """간단한 markdown-ish 문자열을 Notion 블록 배열로 변환.

    지원: # / ## / ### / - / 1. / ```code``` / 일반 단락
    복잡한 변환은 호출자가 직접 children을 구성해서 넘기면 된다.
    """
    blocks: list[dict[str, Any]] = []
    in_code = False
    code_lang = ""
    code_buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("```"):
            if in_code:
                blocks.append(
                    {
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": _text_to_rich_text("\n".join(code_buf)),
                            "language": code_lang or "plain text",
                        },
                    }
                )
                in_code = False
                code_lang = ""
                code_buf = []
            else:
                in_code = True
                code_lang = line[3:].strip()
            continue
        if in_code:
            code_buf.append(line)
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            block_type, content = "heading_1", stripped[2:]
        elif stripped.startswith("## "):
            block_type, content = "heading_2", stripped[3:]
        elif stripped.startswith("### "):
            block_type, content = "heading_3", stripped[4:]
        elif stripped.startswith("- "):
            block_type, content = "bulleted_list_item", stripped[2:]
        elif (
            len(stripped) > 2
            and stripped[0].isdigit()
            and stripped[1:3] == ". "
        ):
            block_type, content = "numbered_list_item", stripped[3:]
        else:
            block_type, content = "paragraph", stripped
        blocks.append(
            {
                "object": "block",
                "type": block_type,
                block_type: {"rich_text": _text_to_rich_text(content)},
            }
        )
    return blocks


def register_tools(mcp: FastMCP) -> None:
    """MCP 서버에 Notion 도구들을 등록한다."""

    @mcp.tool()
    async def search_notion(
        ctx: Context,
        query: Annotated[
            str,
            Field(description="검색어 (빈 문자열이면 최근 항목)", default=""),
        ] = "",
        filter_type: Annotated[
            str,
            Field(
                description="필터: page | database | (빈 값이면 전체)",
                default="",
            ),
        ] = "",
        limit: Annotated[int, Field(description="최대 결과 수", default=20)] = 20,
    ) -> str:
        """Notion 워크스페이스에서 페이지/데이터베이스를 검색한다."""
        logger.info(
            "search_notion 호출: query=%s, filter=%s, limit=%d",
            query,
            filter_type or "all",
            limit,
        )
        client = ctx.request_context.lifespan_context["notion_client"]
        raw = await client.search(
            query=query,
            filter_type=filter_type or None,
            page_size=limit,
        )
        hits = [NotionSearchHit.from_raw(r) for r in raw.get("results", [])]
        result = {
            "has_more": raw.get("has_more", False),
            "next_cursor": raw.get("next_cursor"),
            "results": hits,
        }
        logger.info("search_notion 완료: %d건", len(hits))
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def get_notion_page(
        ctx: Context,
        page_id: Annotated[
            str,
            Field(description="Notion 페이지 ID 또는 URL"),
        ],
        include_body: Annotated[
            bool,
            Field(
                description="True면 본문 블록을 markdown으로 변환해 함께 반환",
                default=True,
            ),
        ] = True,
    ) -> str:
        """Notion 페이지 properties와 (선택) 본문을 조회한다."""
        logger.info("get_notion_page 호출: %s (body=%s)", page_id, include_body)
        client = ctx.request_context.lifespan_context["notion_client"]
        raw = await client.get_page(page_id)
        page = NotionPage.from_raw(raw)
        if include_body:
            blocks = await client.get_all_block_children(page["id"])
            page["body"] = NotionBlock.to_markdown(blocks)
        logger.info("get_notion_page 완료: %s", page_id)
        return json.dumps(page, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def create_notion_page(
        ctx: Context,
        parent_id: Annotated[
            str,
            Field(description="부모 페이지 ID 또는 데이터베이스 ID"),
        ],
        parent_type: Annotated[
            str,
            Field(description="부모 종류: page | database", default="page"),
        ] = "page",
        title: Annotated[
            str,
            Field(
                description=(
                    "페이지 제목. parent_type=database일 때는 properties로 직접 "
                    "title 컬럼을 지정해야 정확하지만, 비워두면 'Name' 컬럼에 적용 시도."
                ),
                default="",
            ),
        ] = "",
        properties_json: Annotated[
            str,
            Field(
                description=(
                    "데이터베이스 row 생성 시 properties JSON 문자열 "
                    '(예: \'{"Status":{"status":{"name":"Doing"}}}\')'
                ),
                default="",
            ),
        ] = "",
        body: Annotated[
            str,
            Field(
                description=(
                    "본문 (간이 markdown). #/##/###, -, 1., ```code``` 지원."
                ),
                default="",
            ),
        ] = "",
    ) -> str:
        """Notion 페이지를 생성한다 (페이지 하위 또는 데이터베이스 row)."""
        logger.info(
            "create_notion_page 호출: parent=%s/%s, title=%s",
            parent_type,
            parent_id,
            title,
        )
        client = ctx.request_context.lifespan_context["notion_client"]

        if parent_type == "database":
            parent = {"database_id": parent_id}
        else:
            parent = {"page_id": parent_id}

        properties: dict[str, Any] = _parse_json_arg(properties_json, "properties_json") or {}
        if title:
            if parent_type == "database":
                properties.setdefault(
                    "Name",
                    {"title": _text_to_rich_text(title)},
                )
            else:
                properties["title"] = {"title": _text_to_rich_text(title)}

        children = _markdown_lines_to_blocks(body) if body else None

        raw = await client.create_page(
            parent=parent,
            properties=properties,
            children=children,
        )
        page = NotionPage.from_raw(raw)
        logger.info("create_notion_page 완료: %s", page.get("id", ""))
        return json.dumps(page, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def update_notion_page(
        ctx: Context,
        page_id: Annotated[str, Field(description="수정할 페이지 ID 또는 URL")],
        properties_json: Annotated[
            str,
            Field(
                description=(
                    "변경할 properties JSON 문자열. 비우면 properties 변경 없음."
                ),
                default="",
            ),
        ] = "",
        archived: Annotated[
            str,
            Field(
                description="archive 토글: 'true' | 'false' | '' (변경 없음)",
                default="",
            ),
        ] = "",
    ) -> str:
        """Notion 페이지의 properties 또는 archive 상태를 변경한다."""
        logger.info("update_notion_page 호출: %s", page_id)
        client = ctx.request_context.lifespan_context["notion_client"]
        properties = _parse_json_arg(properties_json, "properties_json")
        archived_value: bool | None
        if archived == "true":
            archived_value = True
        elif archived == "false":
            archived_value = False
        else:
            archived_value = None

        if properties is None and archived_value is None:
            return json.dumps(
                {"success": False, "error": "변경 항목 없음"},
                ensure_ascii=False,
            )

        raw = await client.update_page(
            page_id=page_id,
            properties=properties,
            archived=archived_value,
        )
        page = NotionPage.from_raw(raw)
        logger.info("update_notion_page 완료: %s", page_id)
        return json.dumps(page, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def append_notion_blocks(
        ctx: Context,
        block_id: Annotated[
            str,
            Field(description="블록 또는 페이지 ID/URL (자식이 추가될 부모)"),
        ],
        body: Annotated[
            str,
            Field(
                description=(
                    "추가할 본문 (간이 markdown). #/##/###, -, 1., ```code``` 지원."
                ),
            ),
        ],
    ) -> str:
        """페이지 또는 블록 하위에 본문 블록을 추가한다."""
        logger.info("append_notion_blocks 호출: %s", block_id)
        client = ctx.request_context.lifespan_context["notion_client"]
        children = _markdown_lines_to_blocks(body)
        if not children:
            return json.dumps(
                {"success": False, "error": "추가할 블록이 없음"},
                ensure_ascii=False,
            )
        raw = await client.append_blocks(block_id, children)
        added = raw.get("results", [])
        logger.info("append_notion_blocks 완료: %s (+%d)", block_id, len(added))
        return json.dumps(
            {"success": True, "added": len(added)},
            ensure_ascii=False,
        )

    @mcp.tool()
    async def get_notion_database(
        ctx: Context,
        database_id: Annotated[
            str,
            Field(description="데이터베이스 ID 또는 URL"),
        ],
    ) -> str:
        """Notion 데이터베이스 메타데이터와 컬럼 스키마를 조회한다."""
        logger.info("get_notion_database 호출: %s", database_id)
        client = ctx.request_context.lifespan_context["notion_client"]
        raw = await client.get_database(database_id)
        db = NotionDatabase.from_raw(raw)
        logger.info("get_notion_database 완료: %s", database_id)
        return json.dumps(db, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def query_notion_database(
        ctx: Context,
        database_id: Annotated[
            str,
            Field(description="데이터베이스 ID 또는 URL"),
        ],
        filter_json: Annotated[
            str,
            Field(
                description=(
                    "Notion filter JSON 문자열 "
                    '(예: \'{"property":"Status","status":{"equals":"Doing"}}\')'
                ),
                default="",
            ),
        ] = "",
        sorts_json: Annotated[
            str,
            Field(
                description=(
                    "Notion sorts JSON 배열 문자열 "
                    '(예: \'[{"property":"Due","direction":"ascending"}]\')'
                ),
                default="",
            ),
        ] = "",
        limit: Annotated[int, Field(description="최대 결과 수", default=20)] = 20,
    ) -> str:
        """Notion 데이터베이스를 filter/sort로 조회한다."""
        logger.info(
            "query_notion_database 호출: %s, limit=%d",
            database_id,
            limit,
        )
        client = ctx.request_context.lifespan_context["notion_client"]
        filter_ = _parse_json_arg(filter_json, "filter_json")
        sorts = _parse_json_arg(sorts_json, "sorts_json")
        raw = await client.query_database(
            database_id,
            filter_=filter_,
            sorts=sorts if isinstance(sorts, list) else None,
            page_size=limit,
        )
        rows = [NotionPage.from_raw(r) for r in raw.get("results", [])]
        result = {
            "has_more": raw.get("has_more", False),
            "next_cursor": raw.get("next_cursor"),
            "results": rows,
        }
        logger.info("query_notion_database 완료: %d건", len(rows))
        return json.dumps(result, ensure_ascii=False, indent=2)