from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GitLabConfig:
    """GitLab 접속 설정."""

    base_url: str
    token: str

    @classmethod
    def from_env(cls) -> GitLabConfig:
        """환경변수에서 설정을 로딩한다.

        필요한 환경변수:
            GITLAB_BASE_URL: GitLab 인스턴스 URL
                예: https://gitlab.com  또는  https://gitlab.사내.co.kr
                (끝의 /api/v4 는 붙이지 않는다 - 클라이언트가 붙인다)
            GITLAB_TOKEN: Personal Access Token
                필요 scope: api  (또는 read_api 만 필요한 경우)
        """
        base_url = os.environ.get("GITLAB_BASE_URL", "")
        token = os.environ.get("GITLAB_TOKEN", "")

        if not all([base_url, token]):
            missing = []
            if not base_url:
                missing.append("GITLAB_BASE_URL")
            if not token:
                missing.append("GITLAB_TOKEN")
            raise ValueError(f"필수 환경변수 누락: {', '.join(missing)}")

        # /api/v4 접미사가 붙어있으면 떼어낸다 (사용자 실수 허용)
        cleaned = base_url.rstrip("/")
        if cleaned.endswith("/api/v4"):
            cleaned = cleaned[: -len("/api/v4")]

        return cls(base_url=cleaned, token=token)