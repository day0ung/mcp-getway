"""PostgreSQL MCP 도구 정의."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from ..postgres.client import PostgresClient
from ..postgres.models import PostgresDDL, PostgresPlan, PostgresRow

logger = logging.getLogger("mcp_gateway.tools.postgres")


def _get_client(ctx: Context, connection: str) -> PostgresClient | dict[str, Any]:
    """lifespan에 등록된 연결 중 이름이 일치하는 클라이언트를 찾는다.

    없으면 사용 가능한 연결 목록을 담은 에러 dict를 돌려준다.
    """
    clients: dict[str, PostgresClient] = ctx.request_context.lifespan_context["postgres_clients"]
    client = clients.get(connection)
    if client is None:
        return {
            "success": False,
            "error": f"연결 '{connection}'을(를) 찾을 수 없습니다.",
            "available_connections": sorted(clients.keys()),
        }
    return client


def register_tools(mcp: FastMCP) -> None:
    """MCP 서버에 PostgreSQL 도구들을 등록한다."""

    @mcp.tool()
    async def postgres_list_connections(ctx: Context) -> str:
        """이 게이트웨이에 설정된 PostgreSQL 연결(DB) 이름 목록을 조회한다."""
        clients: dict[str, PostgresClient] = ctx.request_context.lifespan_context[
            "postgres_clients"
        ]
        result = [
            {"connection": name, "default_schema": client.default_schema}
            for name, client in sorted(clients.items())
        ]
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    async def postgres_list_databases(
        ctx: Context,
        connection: Annotated[
            str,
            Field(
                description=(
                    "이미 등록된 DB 연결 이름 (예: dev). "
                    "그 연결과 같은 서버(호스트)에 있는 전체 데이터베이스 목록을 조회한다"
                )
            ),
        ],
    ) -> str:
        """연결이 속한 PostgreSQL 서버(호스트)의 전체 데이터베이스 목록을 조회한다.

        데이터베이스마다 접속 계정(user/password)이 다를 수 있으므로,
        여기서 발견한 DB를 실제로 조회하려면 .env에 해당 DB 전용 계정으로
        POSTGRES_<NAME>_* 연결을 별도 등록해야 한다.
        """
        logger.info("postgres_list_databases 호출: connection=%s", connection)
        client = _get_client(ctx, connection)
        if isinstance(client, dict):
            return json.dumps(client, ensure_ascii=False)
        rows = await client.list_databases()
        result = PostgresRow.from_raw_list(rows)
        logger.info("postgres_list_databases 완료: %d건", len(result))
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    async def postgres_list_schemas(
        ctx: Context,
        connection: Annotated[str, Field(description="조회할 DB 연결 이름")],
    ) -> str:
        """연결된 데이터베이스 안의 스키마 목록을 조회한다."""
        logger.info("postgres_list_schemas 호출: connection=%s", connection)
        client = _get_client(ctx, connection)
        if isinstance(client, dict):
            return json.dumps(client, ensure_ascii=False)
        rows = await client.list_schemas()
        result = PostgresRow.from_raw_list(rows)
        logger.info("postgres_list_schemas 완료: %d건", len(result))
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    async def postgres_list_tables(
        ctx: Context,
        connection: Annotated[
            str, Field(description="조회할 DB 연결 이름 (postgres_list_connections로 확인)")
        ],
        schema: Annotated[
            str, Field(description="스키마명으로 필터링 (선택, 비우면 전체 스키마)", default="")
        ] = "",
        name_pattern: Annotated[
            str, Field(description="테이블명 부분 일치 검색어 (선택)", default="")
        ] = "",
    ) -> str:
        """PostgreSQL 테이블/뷰 목록을 조회한다."""
        logger.info(
            "postgres_list_tables 호출: connection=%s, schema=%s, pattern=%s",
            connection,
            schema,
            name_pattern,
        )
        client = _get_client(ctx, connection)
        if isinstance(client, dict):
            return json.dumps(client, ensure_ascii=False)
        rows = await client.list_tables(schema=schema or None, name_pattern=name_pattern or None)
        result = PostgresRow.from_raw_list(rows)
        logger.info("postgres_list_tables 완료: %d건", len(result))
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    async def postgres_get_table_schema(
        ctx: Context,
        connection: Annotated[str, Field(description="조회할 DB 연결 이름")],
        table: Annotated[str, Field(description="테이블명")],
        schema: Annotated[
            str,
            Field(
                description="스키마명 (비우면 연결에 설정된 기본 스키마 사용, 기본값 public)",
                default="",
            ),
        ] = "",
    ) -> str:
        """테이블의 컬럼/타입/제약조건/인덱스/코멘트를 조회한다."""
        client = _get_client(ctx, connection)
        if isinstance(client, dict):
            return json.dumps(client, ensure_ascii=False)
        schema = schema or client.default_schema
        logger.info("postgres_get_table_schema 호출: %s / %s.%s", connection, schema, table)
        raw = await client.get_table_schema(schema, table)
        result = {
            "schema": raw["schema"],
            "table": raw["table"],
            "comment": raw["comment"],
            "columns": PostgresRow.from_raw_list(raw["columns"]),
            "constraints": PostgresRow.from_raw_list(raw["constraints"]),
            "indexes": PostgresRow.from_raw_list(raw["indexes"]),
        }
        logger.info("postgres_get_table_schema 완료: %s.%s", schema, table)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    async def postgres_search_schema(
        ctx: Context,
        connection: Annotated[str, Field(description="조회할 DB 연결 이름")],
        keyword: Annotated[
            str,
            Field(description='검색 키워드 (예: "주문", "결제") — 테이블명/컬럼명/코멘트에서 검색'),
        ],
        schema: Annotated[
            str, Field(description="스키마명으로 필터링 (선택)", default="")
        ] = "",
        limit: Annotated[int, Field(description="최대 결과 수", default=50)] = 50,
    ) -> str:
        """테이블명·컬럼명·코멘트에서 키워드로 도메인 스키마를 검색한다."""
        logger.info(
            "postgres_search_schema 호출: connection=%s, keyword=%s, schema=%s",
            connection,
            keyword,
            schema,
        )
        client = _get_client(ctx, connection)
        if isinstance(client, dict):
            return json.dumps(client, ensure_ascii=False)
        rows = await client.search_schema(keyword, schema=schema or None, limit=limit)
        result = PostgresRow.from_raw_list(rows)
        logger.info("postgres_search_schema 완료: %d건", len(result))
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    async def postgres_get_schema_ddl(
        ctx: Context,
        connection: Annotated[str, Field(description="조회할 DB 연결 이름")],
        schema: Annotated[
            str,
            Field(
                description="DDL을 추출할 스키마명 (비우면 연결에 설정된 기본 스키마 사용)",
                default="",
            ),
        ] = "",
        name_pattern: Annotated[
            str, Field(description="테이블명 부분 일치 필터 (선택, 비우면 스키마 전체)", default="")
        ] = "",
    ) -> str:
        """스키마 내 모든 테이블의 CREATE TABLE/INDEX/COMMENT DDL을 생성한다."""
        client = _get_client(ctx, connection)
        if isinstance(client, dict):
            return json.dumps(client, ensure_ascii=False)
        schema = schema or client.default_schema
        logger.info(
            "postgres_get_schema_ddl 호출: connection=%s, schema=%s, pattern=%s",
            connection,
            schema,
            name_pattern,
        )
        raw = await client.get_schema_ddl(schema, name_pattern=name_pattern or None)
        ddl = PostgresDDL.build_schema_ddl(raw)
        result = {
            "schema": schema,
            "table_count": len(raw["table_schemas"]),
            "ddl": ddl,
        }
        logger.info("postgres_get_schema_ddl 완료: %d개 테이블", len(raw["table_schemas"]))
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    async def postgres_execute_query(
        ctx: Context,
        connection: Annotated[str, Field(description="쿼리를 실행할 DB 연결 이름")],
        sql: Annotated[
            str,
            Field(description="실행할 SELECT 쿼리 (단일 문장, SELECT/WITH만 허용)"),
        ],
        limit: Annotated[int, Field(description="최대 반환 행 수", default=200)] = 200,
    ) -> str:
        """사용자가 입력한 읽기 전용 SELECT 쿼리를 실행하고 결과를 반환한다.

        INSERT/UPDATE/DELETE/DDL 등 쓰기 성격의 문장은 거부된다.
        """
        logger.info("postgres_execute_query 호출: connection=%s, sql=%s", connection, sql[:200])
        client = _get_client(ctx, connection)
        if isinstance(client, dict):
            return json.dumps(client, ensure_ascii=False)
        try:
            rows = await client.execute_query(sql, limit=limit)
        except ValueError as exc:
            logger.warning("postgres_execute_query 거부: %s", exc)
            return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)
        result = PostgresRow.from_raw_list(rows)
        logger.info("postgres_execute_query 완료: %d건", len(result))
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    async def postgres_explain_query(
        ctx: Context,
        connection: Annotated[str, Field(description="분석할 DB 연결 이름")],
        sql: Annotated[str, Field(description="분석할 SELECT 쿼리 (EXPLAIN 대상)")],
        analyze: Annotated[
            bool,
            Field(
                description=(
                    "true면 EXPLAIN ANALYZE로 실제 실행해 실측치까지 포함한다. "
                    "쿼리가 실제로 실행되므로 무거운 쿼리는 주의 (기본: false, 추정치만 조회)"
                ),
                default=False,
            ),
        ] = False,
    ) -> str:
        """쿼리 실행 계획을 분석해 인덱스 사용 여부·비용·Seq Scan 여부를 확인한다."""
        logger.info(
            "postgres_explain_query 호출: connection=%s, analyze=%s, sql=%s",
            connection,
            analyze,
            sql[:200],
        )
        client = _get_client(ctx, connection)
        if isinstance(client, dict):
            return json.dumps(client, ensure_ascii=False)
        try:
            plan = await client.explain_query(sql, analyze=analyze)
        except ValueError as exc:
            logger.warning("postgres_explain_query 거부: %s", exc)
            return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)
        summary = PostgresPlan.summarize(plan)
        result = {
            "analyze": analyze,
            "uses_index": PostgresPlan.uses_index(summary),
            "warnings": PostgresPlan.warnings(summary),
            "plan_summary": summary,
            "raw_plan": plan,
        }
        logger.info("postgres_explain_query 완료: uses_index=%s", result["uses_index"])
        return json.dumps(result, ensure_ascii=False, default=str)
