from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GitHubConfig:
    """GitHub 접속 설정."""

    token: str
    base_url: str = "https://api.github.com"
    author_name: str = ""
    author_email: str = ""

    @classmethod
    def from_env(cls) -> GitHubConfig:
        """환경변수에서 설정을 로딩한다.

        필요한 환경변수:
            GITHUB_TOKEN: Personal Access Token (또는 Fine-grained token)
            GITHUB_BASE_URL: GitHub Enterprise 사용 시 지정 (선택, 기본: https://api.github.com)
            GITHUB_AUTHOR_NAME: 커밋 author 이름 (선택)
            GITHUB_AUTHOR_EMAIL: 커밋 author 이메일 (선택)
        """
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            raise ValueError("필수 환경변수 누락: GITHUB_TOKEN")

        base_url = os.environ.get("GITHUB_BASE_URL", "https://api.github.com").rstrip("/")
        author_name = os.environ.get("GITHUB_AUTHOR_NAME", "")
        author_email = os.environ.get("GITHUB_AUTHOR_EMAIL", "")
        return cls(token=token, base_url=base_url, author_name=author_name, author_email=author_email)