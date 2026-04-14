"""JIRA MCP 서버 - CLI 엔트리포인트."""

from __future__ import annotations

import logging

import click
from dotenv import load_dotenv


@click.command()
@click.option(
    "--host",
    default="0.0.0.0",
    help="SSE 서버 바인드 호스트 (기본: 0.0.0.0)",
)
@click.option(
    "--port",
    default=8000,
    type=int,
    help="SSE 서버 포트 (기본: 8000)",
)
def main(host: str, port: int) -> None:
    """JIRA MCP 서버를 실행한다 (SSE 모드)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    load_dotenv()

    from .server import create_mcp

    mcp = create_mcp(host=host, port=port)
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
