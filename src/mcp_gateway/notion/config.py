from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class NotionConfig:
    """Notion API 접속 설정."""

    token: str
    version: str
    base_url: str = "https://api.notion.com"

    @classmethod
    def from_env(cls) -> NotionConfig:
        """환경변수에서 설정을 로딩한다.

        필수: NOTION_TOKEN (Internal Integration Token)
        선택: NOTION_VERSION (기본 2022-06-28)
        """
        token = os.environ.get("NOTION_TOKEN", "")
        version = os.environ.get("NOTION_VERSION", "2022-06-28")

        if not token:
            raise ValueError("필수 환경변수 누락: NOTION_TOKEN")

        return cls(token=token, version=version)