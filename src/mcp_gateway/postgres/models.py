from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID


def _to_jsonable(value: Any) -> Any:
    """asyncpg가 돌려주는 파이썬 값들을 JSON 직렬화 가능한 형태로 변환한다."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    return value


class PostgresRow:
    """asyncpg Record(dict 변환됨)를 JSON 직렬화 가능한 dict로 정리."""

    @staticmethod
    def from_raw(data: dict[str, Any]) -> dict[str, Any]:
        return {k: _to_jsonable(v) for k, v in data.items()}

    @staticmethod
    def from_raw_list(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [PostgresRow.from_raw(r) for r in rows]


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _escape_literal(value: str) -> str:
    return value.replace("'", "''")


class PostgresDDL:
    """get_table_schema() 결과를 사람이 읽는 DDL 텍스트로 변환."""

    @staticmethod
    def build_table_ddl(table_schema: dict[str, Any]) -> str:
        schema = table_schema["schema"]
        table = table_schema["table"]
        qualified = f"{_quote_ident(schema)}.{_quote_ident(table)}"

        body_lines: list[str] = []
        for col in table_schema["columns"]:
            parts = [f'    {_quote_ident(col["column_name"])} {col["data_type"]}']
            if not col["is_nullable"]:
                parts.append("NOT NULL")
            if col.get("default_value"):
                parts.append(f'DEFAULT {col["default_value"]}')
            body_lines.append(" ".join(parts))
        for con in table_schema["constraints"]:
            body_lines.append(f'    CONSTRAINT {_quote_ident(con["name"])} {con["definition"]}')

        statements = [f"CREATE TABLE {qualified} (\n" + ",\n".join(body_lines) + "\n);"]

        for idx in table_schema["indexes"]:
            statements.append(idx["definition"] + ";")

        if table_schema.get("comment"):
            statements.append(
                f"COMMENT ON TABLE {qualified} IS '{_escape_literal(table_schema['comment'])}';"
            )
        for col in table_schema["columns"]:
            if col.get("comment"):
                col_ident = f'{qualified}.{_quote_ident(col["column_name"])}'
                statements.append(
                    f"COMMENT ON COLUMN {col_ident} IS '{_escape_literal(col['comment'])}';"
                )

        return "\n".join(statements)

    @staticmethod
    def build_schema_ddl(schema_ddl: dict[str, Any]) -> str:
        ddls = [
            PostgresDDL.build_table_ddl(table_schema)
            for table_schema in schema_ddl["table_schemas"]
        ]
        return "\n\n".join(ddls)


class PostgresPlan:
    """EXPLAIN (FORMAT JSON) 결과를 인덱스 사용 여부 중심으로 요약."""

    _SCAN_KEYS = (
        "Node Type",
        "Relation Name",
        "Index Name",
        "Startup Cost",
        "Total Cost",
        "Plan Rows",
        "Actual Rows",
        "Actual Total Time",
        "Filter",
        "Index Cond",
        "Rows Removed by Filter",
    )
    _KEY_MAP = {
        "Node Type": "node_type",
        "Relation Name": "relation",
        "Index Name": "index",
        "Startup Cost": "startup_cost",
        "Total Cost": "total_cost",
        "Plan Rows": "plan_rows",
        "Actual Rows": "actual_rows",
        "Actual Total Time": "actual_total_time_ms",
        "Filter": "filter",
        "Index Cond": "index_cond",
        "Rows Removed by Filter": "rows_removed_by_filter",
    }

    @classmethod
    def summarize(cls, plan: dict[str, Any]) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        root = plan.get("Plan", plan)

        def walk(node: dict[str, Any], depth: int) -> None:
            entry: dict[str, Any] = {"depth": depth}
            for raw_key in cls._SCAN_KEYS:
                if raw_key in node:
                    entry[cls._KEY_MAP[raw_key]] = node[raw_key]
            nodes.append(entry)
            for child in node.get("Plans", []):
                walk(child, depth + 1)

        walk(root, 0)
        return nodes

    @staticmethod
    def warnings(summary: list[dict[str, Any]]) -> list[str]:
        warnings: list[str] = []
        for node in summary:
            if node.get("node_type") == "Seq Scan":
                relation = node.get("relation", "?")
                warnings.append(
                    f"Seq Scan 발생: 테이블 '{relation}' 전체를 스캔함 — 인덱스를 타지 않음"
                )
        return warnings

    @staticmethod
    def uses_index(summary: list[dict[str, Any]]) -> bool:
        return any(node.get("index") for node in summary)
