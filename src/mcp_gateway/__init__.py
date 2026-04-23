"""MCP Gateway (Jira / Confluence / GitLab) - CLI 엔트리포인트."""

from __future__ import annotations

import logging
import sys

import click
from dotenv import load_dotenv


@click.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"], case_sensitive=False),
    default="sse",
    help="전송 방식 (기본: sse). Claude Code 등 호스트가 서브프로세스로 띄우는 경우 stdio.",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="SSE 바인드 호스트 (SSE 모드에서만 사용, 기본: 0.0.0.0)",
)
@click.option(
    "--port",
    default=8000,
    type=int,
    help="SSE 포트 (SSE 모드에서만 사용, 기본: 8000)",
)
def main(transport: str, host: str, port: int) -> None:
    """MCP Gateway 서버를 실행한다 (Jira + Confluence + GitLab 툴셋)."""
    # stdio 모드에선 stdout이 MCP 프로토콜 채널이므로 로그는 stderr로만.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )
    load_dotenv()

    from .server import create_mcp

    mcp = create_mcp(host=host, port=port)
    mcp.run(transport=transport.lower())


if __name__ == "__main__":
    main()