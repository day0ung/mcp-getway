# mcp-gateway

Jira / Confluence / GitLab REST API를 한 프로세스에서 MCP로 노출하는 경량 게이트웨이.
SSE 모드로 localhost에 띄워두면, 여러 프로젝트에서 하나의 엔드포인트로 공유해 쓸 수 있다.


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
├── postgres/            → PostgresConfig(다중 연결), PostgresClient, 모델(DDL/EXPLAIN 요약)
│
├── tools/
│   ├── jira.py          → Jira 도구
│   ├── confluence.py    → Confluence 도구
│   ├── gitlab.py        → GitLab 도구 (21개)
│   └── postgres.py      → PostgreSQL 도구 (7개, 읽기 전용)
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

### PostgreSQL (9개, 읽기 전용)

DB 연결 정보는 `.env`가 아니라 **`postgres.databases.json`** 파일에서 관리한다 (`postgres.databases.example.json`을 복사해서 채울 것 — git에는 안 올라감).
여러 DB를 이름(`connection`)으로 구분해 동시에 연결하며, 호스트·계정이 같은 DB끼리는 `clusters`로 묶어 중복 입력을 없앤다:

```json
{
  "clusters": {
    "nonprod": { "host": "...", "user": "readonly", "password": "...", "ssl": false }
  },
  "connections": {
    "dev":  { "cluster": "nonprod", "database": "aptcare2_dev", "schema": "aptcare2" },
    "qa":   { "cluster": "nonprod", "database": "aptcare2_qa" },
    "prod": { "host": "prod-pg...", "database": "aptcare2", "user": "readonly", "password": "...", "ssl": true }
  }
}
```

**반드시 읽기 전용 계정을 사용할 것.** 같은 호스트에 있어도 DB마다 계정이 다를 수 있으므로, 새 DB를 실제로 조회하려면
그 DB 전용 계정으로 `postgres.databases.json`에 연결을 등록해야 한다. 파일이 없으면 PostgreSQL 도구는 그냥 빈 목록으로
동작하고 다른 서비스(Jira/GitLab 등)에는 영향 없음. 파일 위치를 바꾸려면 `.env`에 `POSTGRES_CONFIG_FILE=경로` 지정.

| 도구 | 설명 |
|---|---|
| `postgres_list_connections` | 설정된 연결(DB) 이름 목록 조회 |
| `postgres_list_databases` | 연결과 같은 서버(호스트)에 있는 전체 데이터베이스 목록 조회 (미등록 DB 발견용) |
| `postgres_list_schemas` | 연결된 DB 안의 스키마 목록 조회 |
| `postgres_list_tables` | 테이블/뷰 목록 (스키마·이름 패턴 필터) |
| `postgres_get_table_schema` | 테이블 컬럼/타입/제약조건/인덱스/코멘트 조회 |
| `postgres_search_schema` | 테이블명·컬럼명·코멘트 키워드로 도메인 스키마 검색 |
| `postgres_get_schema_ddl` | 스키마 전체 테이블의 CREATE TABLE/INDEX/COMMENT DDL 생성 |
| `postgres_execute_query` | 사용자가 입력한 SELECT 쿼리 직접 실행 (다중 문장·DDL/DML은 코드 레벨에서 거부) |
| `postgres_explain_query` | EXPLAIN으로 실행 계획 분석 — 인덱스 사용 여부, Seq Scan 경고, 비용 확인 (`analyze=true`면 실제 실행해 실측치 포함) |

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
| `POSTGRES_CONFIG_FILE` | - | PostgreSQL 연결 정보 JSON 파일 경로 (기본: `postgres.databases.json`). 실제 host/user/password는 이 변수가 아니라 그 JSON 파일 안에 있음 — 아래 "PostgreSQL" 섹션 참고 |
