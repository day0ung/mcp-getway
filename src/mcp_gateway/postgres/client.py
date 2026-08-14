from __future__ import annotations

import json
import re
from typing import Any

import asyncpg

from .config import PostgresConnectionConfig

_READ_ONLY_PREFIX = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|grant|revoke|create|call|copy|vacuum|merge|"
    r"lock|reindex|refresh|listen|notify|do)\b",
    re.IGNORECASE,
)


def _validate_read_only_sql(sql: str) -> str:
    """SELECT/WITH 단일 문장인지 검증하고, 끝의 세미콜론을 제거해 반환한다.

    실행 계정이 읽기 전용이더라도, 다중 문장 주입이나 잘못된 쿼리를
    한 번 더 코드 레벨에서 막기 위한 방어선.
    """
    stripped = sql.strip()
    body = stripped[:-1].strip() if stripped.endswith(";") else stripped

    if ";" in body:
        raise ValueError(
            "세미콜론으로 구분된 다중 문장은 허용되지 않습니다. SELECT 단일 문장만 실행하세요."
        )
    if not _READ_ONLY_PREFIX.match(body):
        raise ValueError("SELECT 또는 WITH(CTE)로 시작하는 조회 쿼리만 허용됩니다.")
    if _FORBIDDEN_KEYWORDS.search(body):
        raise ValueError("DDL/DML로 해석될 수 있는 키워드가 포함된 쿼리는 허용되지 않습니다.")

    return body


class PostgresClient:
    """PostgreSQL 조회 전용 클라이언트 (asyncpg 커넥션 풀). 연결 1개(=DB 1개)를 담당한다."""

    def __init__(self, config: PostgresConnectionConfig) -> None:
        self._config = config
        self._pool: asyncpg.Pool | None = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def default_schema(self) -> str:
        return self._config.schema

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
                user=self._config.user,
                password=self._config.password or None,
                ssl="require" if self._config.ssl else None,
                min_size=1,
                max_size=5,
            )
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    # ── 스키마 탐색 ──

    async def list_databases(self) -> list[dict[str, Any]]:
        """이 연결과 같은 서버(호스트)에 있는 데이터베이스 목록을 조회한다.

        pg_database는 접속 권한이 없는 DB의 존재 여부도 보여주는 공유 카탈로그라
        현재 계정으로 실제 접속 가능한지와 무관하게 목록을 볼 수 있다.
        데이터베이스마다 접속 계정(user/password)이 다를 수 있으므로,
        여기 나온 DB를 실제로 조회하려면 해당 DB 전용 계정으로
        .env에 별도 연결(POSTGRES_DATABASES)을 등록해야 한다.
        """
        pool = await self._get_pool()
        rows = await pool.fetch(
            """
            SELECT
                datname AS database,
                datallowconn AS connectable,
                pg_catalog.pg_get_userbyid(datdba) AS owner
            FROM pg_catalog.pg_database
            WHERE datistemplate = false
            ORDER BY datname
            """
        )
        return [dict(r) for r in rows]

    async def list_schemas(self) -> list[dict[str, Any]]:
        """이 연결이 붙어있는 데이터베이스 안의 스키마 목록을 조회한다."""
        pool = await self._get_pool()
        rows = await pool.fetch(
            """
            SELECT
                n.nspname AS schema,
                pg_catalog.pg_get_userbyid(n.nspowner) AS owner,
                obj_description(n.oid, 'pg_namespace') AS comment
            FROM pg_catalog.pg_namespace n
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND n.nspname NOT LIKE 'pg_toast%'
              AND n.nspname NOT LIKE 'pg_temp%'
            ORDER BY n.nspname
            """
        )
        return [dict(r) for r in rows]

    async def list_tables(
        self, schema: str | None = None, name_pattern: str | None = None
    ) -> list[dict[str, Any]]:
        """스키마의 테이블/뷰 목록을 조회한다."""
        query = """
            SELECT
                n.nspname AS schema,
                c.relname AS table_name,
                CASE c.relkind
                    WHEN 'r' THEN 'table'
                    WHEN 'v' THEN 'view'
                    WHEN 'm' THEN 'materialized_view'
                    WHEN 'p' THEN 'partitioned_table'
                    WHEN 'f' THEN 'foreign_table'
                    ELSE c.relkind::text
                END AS table_type,
                obj_description(c.oid, 'pg_class') AS comment
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'v', 'm', 'p', 'f')
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND ($1::text IS NULL OR n.nspname = $1)
              AND ($2::text IS NULL OR c.relname ILIKE $2)
            ORDER BY n.nspname, c.relname
        """
        pool = await self._get_pool()
        pattern = f"%{name_pattern}%" if name_pattern else None
        rows = await pool.fetch(query, schema, pattern)
        return [dict(r) for r in rows]

    async def get_table_schema(self, schema: str, table: str) -> dict[str, Any]:
        """테이블 하나의 컬럼/제약조건/인덱스/코멘트를 조회한다."""
        pool = await self._get_pool()

        columns = await pool.fetch(
            """
            SELECT
                a.attname AS column_name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                NOT a.attnotnull AS is_nullable,
                pg_get_expr(ad.adbin, ad.adrelid) AS default_value,
                col_description(c.oid, a.attnum) AS comment
            FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_catalog.pg_attrdef ad ON ad.adrelid = c.oid AND ad.adnum = a.attnum
            WHERE n.nspname = $1
              AND c.relname = $2
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
            """,
            schema,
            table,
        )

        constraints = await pool.fetch(
            """
            SELECT
                con.conname AS name,
                con.contype AS type,
                pg_get_constraintdef(con.oid) AS definition
            FROM pg_catalog.pg_constraint con
            JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = $1 AND c.relname = $2
            ORDER BY con.contype
            """,
            schema,
            table,
        )

        indexes = await pool.fetch(
            """
            SELECT
                i.relname AS name,
                pg_get_indexdef(ix.indexrelid) AS definition
            FROM pg_catalog.pg_index ix
            JOIN pg_catalog.pg_class c ON c.oid = ix.indrelid
            JOIN pg_catalog.pg_class i ON i.oid = ix.indexrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = $1
              AND c.relname = $2
              AND NOT EXISTS (
                  SELECT 1 FROM pg_catalog.pg_constraint con
                  WHERE con.conindid = ix.indexrelid
              )
            ORDER BY i.relname
            """,
            schema,
            table,
        )

        table_comment_row = await pool.fetchrow(
            """
            SELECT obj_description(c.oid, 'pg_class') AS comment
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = $1 AND c.relname = $2
            """,
            schema,
            table,
        )

        return {
            "schema": schema,
            "table": table,
            "comment": table_comment_row["comment"] if table_comment_row else None,
            "columns": [dict(r) for r in columns],
            "constraints": [dict(r) for r in constraints],
            "indexes": [dict(r) for r in indexes],
        }

    async def search_schema(
        self, keyword: str, schema: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """테이블명/컬럼명/테이블·컬럼 코멘트에서 키워드를 검색한다 (도메인 스키마 검색)."""
        pool = await self._get_pool()
        rows = await pool.fetch(
            """
            SELECT DISTINCT
                n.nspname AS schema,
                c.relname AS table_name,
                a.attname AS column_name,
                col_description(c.oid, a.attnum) AS column_comment,
                obj_description(c.oid, 'pg_class') AS table_comment
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_catalog.pg_attribute a
                ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
            WHERE c.relkind IN ('r', 'v', 'm', 'p', 'f')
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND ($2::text IS NULL OR n.nspname = $2)
              AND (
                  c.relname ILIKE $1
                  OR a.attname ILIKE $1
                  OR obj_description(c.oid, 'pg_class') ILIKE $1
                  OR col_description(c.oid, a.attnum) ILIKE $1
              )
            ORDER BY n.nspname, c.relname, a.attname
            LIMIT $3
            """,
            f"%{keyword}%",
            schema,
            limit,
        )
        return [dict(r) for r in rows]

    async def get_schema_ddl(self, schema: str, name_pattern: str | None = None) -> dict[str, Any]:
        """스키마 내 모든 테이블의 DDL(CREATE TABLE/INDEX/COMMENT)을 생성한다."""
        tables = await self.list_tables(schema=schema, name_pattern=name_pattern)
        table_names = [t["table_name"] for t in tables if t["table_type"] == "table"]
        table_schemas = []
        for table_name in table_names:
            table_schemas.append(await self.get_table_schema(schema, table_name))
        return {"schema": schema, "table_schemas": table_schemas}

    # ── 임의 조회 실행 ──

    async def execute_query(self, sql: str, limit: int = 200) -> list[dict[str, Any]]:
        """읽기 전용 SELECT 쿼리를 실행한다. INSERT/UPDATE/DELETE/DDL은 거부된다."""
        body = _validate_read_only_sql(sql)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                rows = await conn.fetch(body)
        result = [dict(r) for r in rows]
        return result[:limit]

    async def explain_query(self, sql: str, analyze: bool = False) -> dict[str, Any]:
        """쿼리 실행 계획을 EXPLAIN으로 조회한다.

        analyze=True면 EXPLAIN ANALYZE로 실제 실행해 실측치를 포함한다
        (읽기 전용 트랜잭션 안에서 실행되므로 데이터 변경은 없지만, 쿼리가 실제로 실행된다).
        """
        body = _validate_read_only_sql(sql)
        options = "FORMAT JSON"
        if analyze:
            options += ", ANALYZE, BUFFERS"
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                raw = await conn.fetchval(f"EXPLAIN ({options}) {body}")
        plan_list = json.loads(raw) if isinstance(raw, str) else raw
        return plan_list[0] if isinstance(plan_list, list) else plan_list
