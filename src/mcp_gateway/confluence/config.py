from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfluenceConfig:
    """Confluence 접속 설정.

    Jira와 동일한 Atlassian Cloud 사이트/인증을 공유한다.
    별도 도메인이면 CONFLUENCE_BASE_URL로 덮어쓸 수 있다.
    """

    base_url: str
    email: str
    api_token: str

    @classmethod
    def from_env(cls) -> ConfluenceConfig:
        """환경변수에서 설정을 로딩한다.

        우선순위:
            CONFLUENCE_BASE_URL > JIRA_BASE_URL
            CONFLUENCE_EMAIL    > JIRA_EMAIL
            CONFLUENCE_API_TOKEN > JIRA_API_TOKEN
        """
        base_url = os.environ.get("CONFLUENCE_BASE_URL") or os.environ.get("JIRA_BASE_URL", "")
        email = os.environ.get("CONFLUENCE_EMAIL") or os.environ.get("JIRA_EMAIL", "")
        api_token = (
            os.environ.get("CONFLUENCE_API_TOKEN")
            or os.environ.get("JIRA_API_TOKEN", "")
        )

        if not all([base_url, email, api_token]):
            missing = []
            if not base_url:
                missing.append("CONFLUENCE_BASE_URL 또는 JIRA_BASE_URL")
            if not email:
                missing.append("CONFLUENCE_EMAIL 또는 JIRA_EMAIL")
            if not api_token:
                missing.append("CONFLUENCE_API_TOKEN 또는 JIRA_API_TOKEN")
            raise ValueError(f"필수 환경변수 누락: {', '.join(missing)}")

        return cls(
            base_url=base_url.rstrip("/"),
            email=email,
            api_token=api_token,
        )