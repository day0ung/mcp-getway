from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

DEFAULT_CONFIG_FILE = "postgres.databases.json"


@dataclass(frozen=True)
class PostgresClusterConfig:
    """여러 DB가 공유하는 접속정보(호스트/포트/계정) 묶음.

    dev/qa/stage처럼 호스트·계정은 같고 database명만 다른 경우,
    이 클러스터 하나에 접속정보를 몰아넣고 각 연결은 database명만 지정하면 된다.
    """

    name: str
    host: str
    port: int
    user: str
    password: str
    ssl: bool


@dataclass(frozen=True)
class PostgresConnectionConfig:
    """PostgreSQL 개별 연결(DB) 설정."""

    name: str
    host: str
    port: int
    database: str
    user: str
    password: str
    schema: str
    ssl: bool


@dataclass(frozen=True)
class PostgresConfig:
    """여러 PostgreSQL 연결을 이름으로 구분해 관리하는 설정.

    같은 게이트웨이에서 여러 DB(예: dev/qa/stage/prod)를 동시에 다뤄야 하고,
    한 호스트에 등록 안 된 DB가 여러 개 있을 수도 있어서(.env 플랫 변수보다)
    JSON 파일 하나로 관리한다. POSTGRES_CONFIG_FILE(기본: postgres.databases.json)에서 읽는다.
    """

    connections: dict[str, PostgresConnectionConfig] = field(default_factory=dict)
    clusters: dict[str, PostgresClusterConfig] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> PostgresConfig:
        """POSTGRES_CONFIG_FILE이 가리키는 JSON 파일에서 설정을 로딩한다.

        파일 위치는 POSTGRES_CONFIG_FILE 환경변수로 바꿀 수 있고,
        기본값은 실행 디렉터리의 postgres.databases.json 이다.
        파일이 없으면 PostgreSQL을 아직 안 쓰는 배포일 수 있으므로
        에러 없이 빈 연결 맵을 반환한다.

        파일 형식 (postgres.databases.example.json 참고):
            {
              "clusters": {
                "nonprod": {
                  "host": "nonprod-pg.internal",
                  "port": 5432,
                  "user": "readonly",
                  "password": "...",
                  "ssl": false
                }
              },
              "connections": {
                "dev": {
                  "cluster": "nonprod",
                  "database": "aptcare2_dev",
                  "schema": "aptcare2"
                },
                "prod": {
                  "host": "prod-pg.internal",
                  "database": "aptcare2",
                  "user": "readonly",
                  "password": "...",
                  "ssl": true
                }
              }
            }
        """
        path = Path(os.environ.get("POSTGRES_CONFIG_FILE", DEFAULT_CONFIG_FILE))
        if not path.exists():
            return cls()

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} 파싱 실패: {exc}") from exc

        clusters = cls._parse_clusters(raw.get("clusters", {}), path)
        connections = cls._parse_connections(raw.get("connections", {}), clusters, path)
        return cls(connections=connections, clusters=clusters)

    @staticmethod
    def _parse_clusters(
        raw_clusters: dict[str, Any], path: Path
    ) -> dict[str, PostgresClusterConfig]:
        clusters: dict[str, PostgresClusterConfig] = {}
        for name, entry in raw_clusters.items():
            if not _NAME_RE.match(name):
                raise ValueError(
                    f"{path}: clusters의 이름 '{name}'이(가) 올바르지 않습니다. "
                    "영문자로 시작하고 영문/숫자/밑줄만 사용하세요."
                )
            host = entry.get("host", "")
            if not host:
                raise ValueError(f"{path}: 클러스터 '{name}'에 host가 없습니다.")

            clusters[name] = PostgresClusterConfig(
                name=name,
                host=host,
                port=int(entry.get("port", 5432)),
                user=entry.get("user", ""),
                password=entry.get("password", ""),
                ssl=bool(entry.get("ssl", False)),
            )
        return clusters

    @staticmethod
    def _parse_connections(
        raw_connections: dict[str, Any],
        clusters: dict[str, PostgresClusterConfig],
        path: Path,
    ) -> dict[str, PostgresConnectionConfig]:
        connections: dict[str, PostgresConnectionConfig] = {}
        for name, entry in raw_connections.items():
            if not _NAME_RE.match(name):
                raise ValueError(
                    f"{path}: connections의 이름 '{name}'이(가) 올바르지 않습니다. "
                    "영문자로 시작하고 영문/숫자/밑줄만 사용하세요."
                )

            cluster_name = entry.get("cluster", "")
            cluster = clusters.get(cluster_name) if cluster_name else None
            if cluster_name and cluster is None:
                raise ValueError(
                    f"{path}: 연결 '{name}'이 참조하는 클러스터 '{cluster_name}'을(를) "
                    "clusters에서 찾을 수 없습니다."
                )

            host = entry.get("host") or (cluster.host if cluster else "")
            port = int(entry.get("port") or (cluster.port if cluster else 5432))
            database = entry.get("database", "")
            user = entry.get("user") or (cluster.user if cluster else "")
            password = entry.get("password") or (cluster.password if cluster else "")
            schema = entry.get("schema", "public")
            ssl_raw = entry.get("ssl")
            ssl = bool(ssl_raw) if ssl_raw is not None else (cluster.ssl if cluster else False)

            missing = []
            if not host:
                missing.append("host (또는 cluster)")
            if not database:
                missing.append("database")
            if not user:
                missing.append("user (또는 cluster)")
            if missing:
                raise ValueError(f"{path}: 연결 '{name}'에 필수 값 누락: {', '.join(missing)}")

            connections[name] = PostgresConnectionConfig(
                name=name,
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                schema=schema,
                ssl=ssl,
            )
        return connections
