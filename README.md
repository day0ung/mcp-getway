# mcp-gateway

JIRA REST API를 직접 호출하는 경량 MCP(Model Context Protocol) 서버.
SSE(Server-Sent Events) 모드로 localhost에 띄워두면, 여러 프로젝트에서 공유하여 사용할 수 있다.

## 왜 만들었나

Atlassian 공식 MCP 서버(`mcp.atlassian.com`)는 조직 권한 문제로 API 토큰 접근이 차단된다.
JIRA REST API 직접 호출(Basic Auth)은 정상 동작하므로, 커스텀 MCP 서버를 구축하여 Claude Code에서 JIRA를 사용한다.

## 기술 스택

- Python 3.10+
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (FastMCP)
- httpx (async HTTP 클라이언트)
- Click (CLI)

## 패키지 구조

```
src/mcp_atlassian/
│
├── __init__.py        → CLI 엔트리포인트 (Click)
├── __main__.py        → python -m mcp_atlassian 지원
├── server.py          → FastMCP 서버 + lifespan
│
├── tools/
│   └── jira.py        → 6개 MCP 도구 정의
│
├── jira/
│   ├── config.py      → JiraConfig (환경변수 로딩)
│   ├── client.py      → JiraClient (httpx + Basic Auth)
│   └── models.py      → JiraIssue, JiraComment, JiraTransition
│
└── utils/
    └── adf.py         → ADF 파서 (parse_adf, text_to_adf)
```

## 제공 도구

| 도구명 | 설명 |
|--------|------|
| `get_issue` | 이슈 상세 조회 |
| `get_comments` | 이슈 댓글 조회 |
| `add_comment` | 이슈에 댓글 추가 |
| `search_issues` | JQL로 이슈 검색 |
| `get_transitions` | 이슈 상태 변경 가능 목록 조회 |
| `transition_issue` | 이슈 상태 변경 |

## 사전 요구사항

서버를 쓰려는 사람 PC에 다음이 필요하다:

1. **Python 3.10+** 설치
2. `pip install -e .`로 의존성 설치
3. `.env` 파일에 본인 JIRA 인증 정보 세팅
4. `python -m mcp_atlassian`로 서버 실행

## 설치 및 실행

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
# powershell   
py -m venv .venv

source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate     # macOS/Linux

# 의존성 설치
pip install -e .

# 환경변수 설정
cp .env.example .env
# .env 파일에 JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN 입력

# SSE 서버 실행 (기본: http://0.0.0.0:8000)
python -m mcp_atlassian

# 포트 충돌 시 (ERROR: [Errno 10048]) 기존 프로세스 종료 후 재실행
netstat -ano | findstr :8000
taskkill /PID <PID번호> /F

# 포트/호스트 변경
python -m mcp_atlassian --port 9000 --host 127.0.0.1
```

## Claude Code 연동

서버를 한 번 띄워두고 여러 프로젝트에서 공유할 수 있다.

먼저 서버를 실행한다:
```bash
cd /path/to/mcp-gateway
source .venv/Scripts/activate
python -m mcp_atlassian
```

다른 프로젝트의 `.claude/settings.json` 또는 `~/.claude/settings.json`에 추가:
```json
{
  "mcpServers": {
    "atlassian": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

## 문서

- [JIRA API 참고 가이드](docs/jira-mcp-server-guide.md)
- [아키텍처 설계](docs/architecture.md)