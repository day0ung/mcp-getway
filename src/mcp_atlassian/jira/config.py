from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class JiraConfig:
    """JIRA 접속 설정."""

    base_url: str
    email: str
    api_token: str

    @classmethod
    def from_env(cls) -> JiraConfig:
        """환경변수에서 설정을 로딩한다.

        필요한 환경변수:
            JIRA_BASE_URL: JIRA 사이트 URL
            JIRA_EMAIL: 인증 이메일
            JIRA_API_TOKEN: API 토큰
        """
        base_url = os.environ.get("JIRA_BASE_URL", "")
        email = os.environ.get("JIRA_EMAIL", "")
        api_token = os.environ.get("JIRA_API_TOKEN", "")

        if not all([base_url, email, api_token]):
            missing = []
            if not base_url:
                missing.append("JIRA_BASE_URL")
            if not email:
                missing.append("JIRA_EMAIL")
            if not api_token:
                missing.append("JIRA_API_TOKEN")
            raise ValueError(f"필수 환경변수 누락: {', '.join(missing)}")

        return cls(
            base_url=base_url.rstrip("/"),
            email=email,
            api_token=api_token,
        )
