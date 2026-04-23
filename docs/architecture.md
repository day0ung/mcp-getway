# MCP Gateway 설계 문서

## 개요

Jira / Confluence / GitLab REST API를 직접 호출하는 경량 커스텀 MCP 서버.
한 프로세스에서 세 서비스의 툴을 동시에 노출하여, 하나의 SSE 엔드포인트로 Claude Code가 모두 사용하게 한다.

## 참고 레포지토리

| 참고 | 용도 |
|---|---|
| [sooperset/mcp-atlassian](https://github.com/sooperset/mcp-atlassian) | 전체 패키지 구조 · lifespan 패턴 참고 |
| [zereight/gitlab-mcp](https://github.com/zereight/gitlab-mcp) (TypeScript) | GitLab 툴 범위 선정 및 엔드포인트 매핑 참고 (141개 → 핵심 21개로 축약) |

| 비교 항목 | sooperset/mcp-atlassian | zereight/gitlab-mcp | mcp-gateway (본 프로젝트) |
|---|---|---|---|
| 대상 서비스 | Jira + Confluence | GitLab | **Jira + Confluence + GitLab** |
| 언어 | Python | TypeScript | **Python** |
| 도구 수 | 73개 | 141개 | **Jira 10개 + Confluence 5개 + GitLab 21개** |
| 인증 방식 | OAuth, PAT, Basic Auth, BYOT | PAT, OAuth, MCP OAuth, Remote Auth | **Basic Auth (Atlassian) + PRIVATE-TOKEN (GitLab)** |
| Transport | stdio, SSE, streamable-http | stdio, SSE, streamable-http | **stdio, SSE** |
| 구조 패턴 | Mixin 기반 대규모 구성 | 단일 index.ts(10k줄) + toolset 필터 | **서비스별 서브모듈(config/client/models) 경량 반복** |

## 폴더 구조

```
mcp-gateway/
├── pyproject.toml              # 패키지 설정 + 의존성
├── .env.example                # 환경변수 템플릿
├── .mcp.json                   # 이 레포 자체 개발용 (stdio)
├── README.md
├── docs/
│   ├── architecture.md            # 본 문서
│   ├── jira-mcp-server-guide.md   # Jira API 참고
│   └── claude-code-config.md      # Claude Code 설정이 어떻게 읽히는지 (부록)
│
└── src/
    └── mcp_gateway/
        ├── __init__.py            # CLI 엔트리포인트 (Click)
        ├── __main__.py            # python -m mcp_gateway
        ├── server.py              # FastMCP 서버 + lifespan (3개 클라이언트 관리)
        │
        ├── jira/                  # Jira 서브모듈
        │   ├── config.py            # JiraConfig
        │   ├── client.py            # httpx 기반 Jira REST API v3 클라이언트
        │   └── models.py            # JiraIssue, JiraComment, JiraTransition
        │
        ├── confluence/            # Confluence 서브모듈 (Jira와 동일 패턴)
        │   ├── config.py            # ConfluenceConfig (Jira 인증 공유 가능)
        │   ├── client.py            # httpx 기반 Confluence v2 + CQL v1
        │   └── models.py            # ConfluencePage, ConfluenceSearchHit
        │
        ├── gitlab/                # GitLab 서브모듈 (동일 패턴)
        │   ├── config.py            # GitLabConfig
        │   ├── client.py            # httpx 기반 GitLab REST API v4
        │   └── models.py            # GitLabProject, GitLabMergeRequest, GitLabBranch,
        │                            # GitLabCommit, GitLabDiff
        │
        ├── tools/                 # MCP 도구 등록
        │   ├── jira.py              # register_tools(mcp) → Jira 툴
        │   ├── confluence.py        # register_tools(mcp) → Confluence 툴
        │   └── gitlab.py            # register_tools(mcp) → GitLab 툴 (21개)
        │
        └── utils/
            └── adf.py             # Atlassian Document Format 파서
```

## 설계 원칙

1. **서비스당 서브모듈 3종(`config` / `client` / `models`) 패턴 반복**
   새 서비스 추가 시 이 세 파일만 만들고 `tools/<service>.py` + `server.py`에 등록 한 줄이면 끝. Jira를 만들고 같은 틀로 Confluence를 붙이고, 동일한 틀로 GitLab을 붙였다.

2. **도구 레이어는 얇게**
   `tools/*.py`는 `@mcp.tool()` 데코레이터 + 인자 파싱 + `client` 호출 + `models`로 정돈해서 JSON 문자열 반환. 비즈니스 로직 없음. 복잡한 변환은 `models`에 가둠.

3. **외부 의존성 최소화**
   `mcp`, `httpx`, `click`, `python-dotenv` 4개. FastMCP가 SSE/stdio 둘 다 처리하므로 웹 프레임워크 별도 도입 안 함.

4. **응답은 항상 JSON 문자열**
   MCP는 `text` 콘텐츠 블록으로 응답을 주고받는다. 모든 툴은 `json.dumps(..., ensure_ascii=False, indent=2)` 로 반환 — LLM이 한글을 그대로 읽을 수 있게 `ensure_ascii=False` 필수.

## 모듈별 역할

### `src/mcp_gateway/__init__.py` — CLI 엔트리포인트

- Click 기반 CLI
- `python-dotenv`로 `.env` 로딩
- `--transport` (기본: sse) — `sse` | `stdio`
- `--host` (기본: 0.0.0.0) — SSE 바인드
- `--port` (기본: 8000) — SSE 포트
- `logging.basicConfig(stream=sys.stderr)` — stdio 모드에선 stdout이 MCP 프로토콜 채널이므로 로그는 stderr로만

### `src/mcp_gateway/server.py` — MCP 서버

- `FastMCP("MCP Gateway", lifespan=..., host=..., port=...)` 인스턴스 생성
- `lifespan`에서 3개 Config를 env에서 로딩하고 3개 Client를 초기화. yield로 dict를 노출 → 각 툴에서 `ctx.request_context.lifespan_context["jira_client"]` 식으로 꺼내 씀
- 종료 시 `await client.close()` 세 번 호출
- `register_jira_tools(mcp)` / `register_confluence_tools(mcp)` / `register_gitlab_tools(mcp)` 로 툴 주입

### 서비스별 `config.py` — 환경변수 → 설정 데이터클래스

| 서비스 | 필수 변수 | 비고 |
|---|---|---|
| Jira | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | — |
| Confluence | 없음 (Jira 자격증명 자동 공유) | `CONFLUENCE_BASE_URL` / `_EMAIL` / `_API_TOKEN`으로 개별 지정 가능 |
| GitLab | `GITLAB_BASE_URL`, `GITLAB_TOKEN` | `/api/v4` 접미사는 client가 자동 부착, `config`에서 떼어냄 |

전부 `from_env()` 클래스메서드로 생성, 누락 시 명확한 에러 메시지 throw.

### 서비스별 `client.py` — httpx 기반 비동기 클라이언트

공통 패턴:

```python
class XxxClient:
    def __init__(self, config):
        self._client = httpx.AsyncClient(
            base_url=...,
            headers={...},   # Basic Auth or PRIVATE-TOKEN
            timeout=30.0,
        )
    async def close(self): await self._client.aclose()
    async def get/post/put/delete(...): response.raise_for_status() 후 json()
    # + 서비스별 엔드포인트 메서드들
```

### 서비스별 `models.py` — 응답 파서

REST API 원본 응답에서 LLM이 읽기 쉬운 key만 뽑아 dict로 재구성. 예:

```python
class GitLabProject:
    @staticmethod
    def summary(data: dict) -> dict:
        return {
            "id": data.get("id"),
            "path_with_namespace": ...,
            "default_branch": ...,
            ...
        }
```

LLM 토큰 절약 + 원본 스키마 변화에 대한 완충 역할. 필요하면 `summary`/`detail` 등 여러 함수로 분기.

### `src/mcp_gateway/tools/<service>.py` — MCP 도구 등록

`register_tools(mcp: FastMCP) -> None` 함수 안에서 `@mcp.tool()` 데코레이터로 각 툴을 선언. 클라이언트는 `ctx`로 주입받음:

```python
def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_projects(ctx: Context, search: ..., ...) -> str:
        client = ctx.request_context.lifespan_context["gitlab_client"]
        raw = await client.list_projects(...)
        return json.dumps([GitLabProject.summary(p) for p in raw], ...)
```

### `src/mcp_gateway/utils/adf.py` — ADF 파서

Jira API v3 댓글 body의 ADF(Atlassian Document Format) 처리. 양방향:

- `parse_adf(node) -> str` — ADF 트리 → 평문 텍스트 (재귀)
- `text_to_adf(text) -> dict` — 평문 → ADF (댓글 작성 시)

## 도구 요약

자세한 목록은 [README.md](../README.md#제공-도구) 참고.

| 서비스 | 도구 수 | 영역 |
|---|---|---|
| Jira | 10 | 이슈 CRUD, 댓글 CRUD, JQL 검색, 상태 전이 |
| Confluence | 5 | 페이지 CRUD, CQL 검색 |
| GitLab | 21 | 프로젝트/레포 조회, 브랜치 CRUD, MR CRUD, MR 리뷰 (스레드/draft note), 코드 diff |

## 인증 흐름

```
.env
  │
  ├──── JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN ────┐
  │                                                    │
  ├──── CONFLUENCE_* (선택, 없으면 JIRA_* 공유) ────────┤
  │                                                    │
  └──── GITLAB_BASE_URL, GITLAB_TOKEN ────────────────┐│
                                                     ││
          lifespan() 에서 from_env() 호출             ││
                          ↓                          ││
          JiraClient / ConfluenceClient / GitLabClient
                          ↓
                httpx.AsyncClient 각각
                   ├── Jira:       Authorization: Basic base64(email:token)
                   ├── Confluence: 동일 (Jira와 자격증명 공유)
                   └── GitLab:     PRIVATE-TOKEN: <pat>
                          ↓
         각 서비스 REST API (v3 / v2 / v4)
```

## 의존성

```toml
[project]
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",           # FastMCP
    "httpx>=0.27.0",        # async HTTP 클라이언트
    "click>=8.0.0",         # CLI
    "python-dotenv",        # .env 로딩
]

[project.scripts]
mcp-gateway = "mcp_gateway:main"
```

추가 의존성 없음. FastMCP가 SSE 서버/stdio 둘 다 처리하므로 별도 ASGI 프레임워크 불필요.

## 확장 포인트

새 서비스(예: Bitbucket)를 붙이고 싶으면:

1. `src/mcp_gateway/bitbucket/{config.py, client.py, models.py}` 생성
2. `src/mcp_gateway/tools/bitbucket.py` 에 `register_tools(mcp)` 작성
3. `src/mcp_gateway/server.py` 의 `lifespan` 과 `create_mcp`에 3줄 추가 (import, client 초기화, register 호출)
4. `.env.example` + `README.md` 환경변수/도구 섹션 갱신

기존 서비스는 건드리지 않고 독립적으로 증설 가능.