# mcp-gateway

Jira / Confluence / GitLab REST API를 한 프로세스에서 MCP로 노출하는 경량 게이트웨이.
SSE 모드로 localhost에 띄워두면, 여러 프로젝트에서 하나의 엔드포인트로 공유해 쓸 수 있다.

## 왜 만들었나

- Atlassian 공식 MCP 서버(`mcp.atlassian.com`)는 조직 권한 문제로 API 토큰 접근이 차단됨. REST API(Basic Auth) 직접 호출로 우회.
- GitLab은 `@zereight/mcp-gitlab` 같은 npm 기반 서버가 있지만, 사내 인프라(Python-only, Node 미설치 환경)와 맞추고 스코프(141개 → 핵심 21개)를 줄이기 위해 직접 포팅.
- 결과적으로 **한 프로세스 = 하나의 SSE 엔드포인트**로 Jira + Confluence + GitLab 툴을 Claude Code에서 모두 쓸 수 있다.

## 기술 스택

- Python 3.10+
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (FastMCP)
- httpx (async HTTP)
- Click (CLI)

## 패키지 구조

```
src/mcp_gateway/
│
├── __init__.py          → CLI 엔트리포인트 (Click)
├── __main__.py          → python -m mcp_gateway 지원
├── server.py            → FastMCP 서버 + lifespan (3개 클라이언트 관리)
│
├── jira/                → JiraConfig, JiraClient, 모델
├── confluence/          → ConfluenceConfig, ConfluenceClient, 모델
├── gitlab/              → GitLabConfig, GitLabClient, 모델
│
├── tools/
│   ├── jira.py          → Jira 도구
│   ├── confluence.py    → Confluence 도구
│   └── gitlab.py        → GitLab 도구 (21개)
│
└── utils/
    └── adf.py           → Atlassian Document Format 파서
```

## 제공 도구

### Jira

| 도구 | 설명 |
|---|---|
| `get_issue` | 이슈 상세 조회 |
| `get_comments` | 이슈 댓글 조회 |
| `add_comment` / `update_comment` / `delete_comment` | 댓글 작성/수정/삭제 |
| `create_issue` / `update_issue` | 이슈 생성/수정 |
| `search_issues` | JQL 검색 |
| `get_transitions` / `transition_issue` | 상태 전이 |

### Confluence

페이지 조회/검색/생성/수정/삭제.

### GitLab (21개)

| 분류 | 도구 |
|---|---|
| 프로젝트/레포 | `list_projects`, `get_project`, `get_file_contents`, `get_repository_tree`, `list_commits` |
| 브랜치 | `list_branches`, `create_branch`, `get_branch_diffs` |
| MR 기본 | `list_merge_requests`, `get_merge_request`, `create_merge_request`, `get_merge_request_diffs`, `approve_merge_request`, `merge_merge_request` |
| MR 리뷰 (2단계) | `list_merge_request_changed_files` (파일 경로만) → `get_merge_request_file_diff` (지정 파일 diff 배치) |
| MR 코멘트 | `create_note`, `mr_discussions`, `create_merge_request_thread`, `create_draft_note`, `bulk_publish_draft_notes` |

## 사전 요구사항

1. Python 3.10+
2. `.env` 파일에 Atlassian + GitLab 인증 정보
3. `pip install -e .`

## 설치 및 실행

```bash
# 가상환경
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate     # macOS/Linux

# 의존성 설치
pip install -e .

# 환경변수
cp .env.example .env
# .env에 JIRA_*, GITLAB_BASE_URL, GITLAB_TOKEN 채우기

# SSE 서버 실행 (기본: http://0.0.0.0:8000)
python -m mcp_gateway
# 또는
mcp-gateway

# 포트/호스트 변경
mcp-gateway --port 9000 --host 127.0.0.1

# 포트 충돌 시 (ERROR: [Errno 10048])
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

## Claude Code 연동

한 번 띄워두면 여러 프로젝트가 공유한다.

```bash
cd /path/to/mcp-gateway
source .venv/Scripts/activate
mcp-gateway
```

그 다음, **사용하고 싶은 다른 프로젝트 쪽**에 설정을 추가. 두 위치 중 택일.

### 옵션 A — 사용자 전역 (모든 프로젝트에서 쓰고 싶을 때, 추천)

`C:\Users\<USER>\.claude\settings.json` (macOS/Linux: `~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "gateway": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

→ 이 PC의 Claude Code는 앞으로 모든 프로젝트에서 `mcp__gateway__*` 툴을 쓸 수 있다.

### 옵션 B — 프로젝트 한정

해당 프로젝트 루트의 `.claude/settings.json`:

```json
{
  "mcpServers": {
    "gateway": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

→ 그 프로젝트에서만 노출됨.

### 옵션 C — 이 레포 자체 (stdio)

`.mcp.json` (이미 이 레포에 있음):

```json
{
  "mcpServers": {
    "gateway": {
      "command": "C:/~/.venv/Scripts/mcp-gateway.exe",
      "args": ["--transport", "stdio"]
    }
  }
}
```

→ 서버가 떠있지 않아도 Claude가 실행 시 자동으로 서브프로세스로 띄워준다.

### 다른 PC에서 이 서버를 쓰려면

- 서버 실행은 지금도 `--host 0.0.0.0`이라 외부에서 붙을 수 있음.
- 클라이언트 PC의 `settings.json`에서 `localhost` 대신 **서버 PC의 IP**를 넣는다:
  ```json
  { "mcpServers": { "gateway": { "url": "http://192.168.x.x:8000/sse" } } }
  ```
- 서버 PC 방화벽에서 8000 포트 허용 필요.
- 양쪽 모두 사내망(DNS/ Atlassian 접근)에 닿아야 함.

### 반영되려면 Claude Code를 재시작해야 한다

설정 파일을 수정했다면 Claude Code를 완전히 종료 후 다시 실행해야 새 서버에 연결된다. 서버만 재기동하는 건 소용없음 (클라이언트 쪽에서 설정을 다시 읽어야 함).

## 환경변수 레퍼런스

| 변수 | 필수 | 설명 |
|---|---|---|
| `JIRA_BASE_URL` | ✅ | `https://{도메인}.atlassian.net` |
| `JIRA_EMAIL` | ✅ | Atlassian 계정 이메일 |
| `JIRA_API_TOKEN` | ✅ | Atlassian API 토큰 |
| `CONFLUENCE_BASE_URL` / `_EMAIL` / `_API_TOKEN` | - | Confluence가 Jira와 다른 인스턴스일 때만 |
| `GITLAB_BASE_URL` | ✅ | GitLab 루트 URL (예: `https://gitlab.사내.co.kr`). `/api/v4` 붙이지 말 것 |
| `GITLAB_TOKEN` | ✅ | GitLab Personal Access Token (scope: `api`) |

## 문서

- [JIRA API 참고 가이드](docs/jira-mcp-server-guide.md)
- [아키텍처 설계](docs/architecture.md)
- [Claude Code는 이 설정을 어떻게 읽는가 (부록)](docs/claude-code-config.md)