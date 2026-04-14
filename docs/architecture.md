# MCP JIRA 서버 설계 문서

## 개요
JIRA REST API를 직접 호출하는 경량 커스텀 MCP 서버를 구축한다.

## 참고 레포지토리

[sooperset/mcp-atlassian](https://github.com/sooperset/mcp-atlassian)의 아키텍처를 참고하되,
JIRA 전용 6개 도구 + Basic Auth로 경량화한다.

| 비교 항목 | mcp-atlassian | mcp-gateway (본 프로젝트) |
|-----------|---------------|--------------------------|
| 대상 서비스 | JIRA + Confluence | JIRA 전용 |
| 도구 수 | 73개 | 6개 |
| 인증 방식 | OAuth, PAT, Basic Auth, BYOT | Basic Auth 전용 |
| Transport | stdio, SSE, streamable-http | SSE |
| 구조 패턴 | Mixin 기반 대규모 구성 | 단일 클라이언트 경량 구성 |

## 폴더 구조

```
mcp-gateway/
├── pyproject.toml              # 패키지 설정 + 의존성
├── .env.example                # 환경변수 템플릿
├── README.md
├── docs/
│   ├── jira-mcp-server-guide.md  # JIRA API 참고 가이드
│   └── architecture.md           # 본 문서
│
└── src/
    └── mcp_atlassian/
        ├── __init__.py           # CLI 엔트리포인트 (Click)
        ├── server.py             # FastMCP 서버 인스턴스 + lifespan
        ├── tools/
        │   ├── __init__.py
        │   └── jira.py           # 6개 도구 정의
        ├── jira/
        │   ├── __init__.py
        │   ├── config.py         # JiraConfig 데이터클래스
        │   ├── client.py         # httpx 기반 JIRA REST API 클라이언트
        │   └── models.py         # JiraIssue, JiraComment 등 모델
        └── utils/
            ├── __init__.py
            └── adf.py            # ADF 파서
```

## 모듈별 역할

### `src/mcp_atlassian/__init__.py` - CLI 엔트리포인트

- Click 기반 CLI로 서버 실행
- `python-dotenv`로 `.env` 파일 로딩
- `--host` 옵션 (기본: 0.0.0.0) — SSE 바인드 호스트
- `--port` 옵션 (기본: 8000) — SSE 포트

### `src/mcp_atlassian/server.py` - MCP 서버

- `FastMCP` 인스턴스 생성
- `lifespan`에서 `JiraConfig` 로딩 및 `JiraClient` 초기화
- Context를 통해 도구에 클라이언트 주입

### `src/mcp_atlassian/tools/jira.py` - 도구 정의

`@mcp.tool()` 데코레이터로 6개 도구 등록:

| 도구명 | HTTP 메서드 | 엔드포인트 | 설명 |
|--------|------------|-----------|------|
| `get_issue` | GET | `/rest/api/3/issue/{issueKey}` | 이슈 상세 조회 |
| `get_comments` | GET | `/rest/api/3/issue/{issueKey}/comment` | 이슈 댓글 조회 |
| `add_comment` | POST | `/rest/api/3/issue/{issueKey}/comment` | 이슈에 댓글 추가 |
| `search_issues` | GET | `/rest/api/3/search?jql=...` | JQL로 이슈 검색 |
| `get_transitions` | GET | `/rest/api/3/issue/{issueKey}/transitions` | 상태 변경 가능 목록 |
| `transition_issue` | POST | `/rest/api/3/issue/{issueKey}/transitions` | 이슈 상태 변경 |

### `src/mcp_atlassian/jira/config.py` - 설정

```python
@dataclass
class JiraConfig:
    base_url: str       # JIRA 사이트 URL
    email: str          # 인증 이메일
    api_token: str      # API 토큰

    @classmethod
    def from_env(cls) -> "JiraConfig":
        """환경변수에서 설정 로딩"""
```

환경변수:

| 변수명 | 설명 | 예시                               |
|--------|------|----------------------------------|
| `JIRA_BASE_URL` | JIRA 사이트 URL | `https://{domain}.atlassian.net` |
| `JIRA_EMAIL` | 인증 이메일 | `dayoung@gmail.co.kr`            |
| `JIRA_API_TOKEN` | API 토큰 | (settings.json에서 관리)             |

### `src/mcp_atlassian/jira/client.py` - API 클라이언트

- `httpx.AsyncClient` 래핑
- Basic Auth 헤더 자동 설정: `Authorization: Basic base64(이메일:API토큰)`
- GET/POST 메서드 제공
- 에러 핸들링 (401, 403, 404 등)

### `src/mcp_atlassian/jira/models.py` - 데이터 모델

- `JiraIssue`: 이슈 응답 파싱 (키, 요약, 상태, 담당자, 설명 등)
- `JiraComment`: 댓글 응답 파싱 (작성자, 본문, 작성일)
- `JiraTransition`: 트랜지션 응답 파싱 (ID, 이름)
- 각 모델은 `to_dict()` 메서드로 정리된 dict 반환

### `src/mcp_atlassian/utils/adf.py` - ADF 파서

JIRA API v3 댓글 body의 ADF(Atlassian Document Format) 처리:

- `parse_adf(adf_node) -> str`: ADF → 텍스트 변환 (재귀)
- `text_to_adf(text) -> dict`: 텍스트 → ADF 변환 (댓글 작성용)

파싱 대상 노드:

| 노드 타입 | 처리 |
|-----------|------|
| `text` | `node.text` 추출 |
| `mention` | `node.attrs.text` 추출 (예: @사용자명) |
| `hardBreak` | 줄바꿈(`\n`) |
| `content` | 자식 노드 재귀 탐색 |

## 인증 흐름

```
환경변수(.env)
    ↓
JiraConfig.from_env()
    ↓
JiraClient(config)
    ↓
httpx.AsyncClient
    └── Authorization: Basic base64(email:token)
        ↓
    JIRA REST API v3
```

## 의존성

```toml
[project]
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",
    "httpx>=0.27.0",
    "click>=8.0.0",
    "python-dotenv",
]
```

## Claude Code 연동

서버를 먼저 실행한 뒤, 다른 프로젝트의 settings.json에 URL만 등록:

```json
{
  "mcpServers": {
    "atlassian": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

