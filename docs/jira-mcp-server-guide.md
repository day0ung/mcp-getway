# JIRA MCP 서버 구축 가이드

## 배경

- JIRA REST API를 직접 호출하는 커스텀 MCP 서버를 구축

## JIRA 접속 정보

| 항목 | 값                                |
|------|----------------------------------|
| 사이트 | https://aegisepdev.atlassian.net |
| 프로젝트 키 | APTI                             |
| 인증 방식 | Basic Auth (이메일:API토큰)           |
| 이메일 | dayoung@gmail.co.kr              |
| API 토큰 | (settings.json에서 관리)             |

## 인증 방식

JIRA REST API는 Basic Auth를 사용한다. `이메일:API토큰`을 Base64 인코딩하여 Authorization 헤더에 전달.

```
Authorization: Basic base64(이메일:API토큰)
```


## 필요한 JIRA REST API 엔드포인트

### 1. 이슈 조회
```
GET /rest/api/3/issue/{issueKey}
```

### 2. 이슈 댓글 조회
```
GET /rest/api/3/issue/{issueKey}/comment
```

### 3. 이슈 댓글 작성
```
POST /rest/api/3/issue/{issueKey}/comment
Content-Type: application/json

{
  "body": {
    "type": "doc",
    "version": 1,
    "content": [
      {
        "type": "paragraph",
        "content": [{ "type": "text", "text": "댓글 내용" }]
      }
    ]
  }
}
```

### 4. JQL 이슈 검색
```
GET /rest/api/3/search?jql={JQL_QUERY}&maxResults=50
```

### 5. 이슈 상태 변경 (트랜지션)
```
# 가능한 트랜지션 조회
GET /rest/api/3/issue/{issueKey}/transitions

# 트랜지션 실행
POST /rest/api/3/issue/{issueKey}/transitions
{ "transition": { "id": "트랜지션ID" } }
```

## MCP 서버 구현 요구사항

### 기술 스택
- Python
- `mcp` 패키지 (MCP Python SDK)
- `httpx` 또는 `requests` (JIRA REST API 호출)

### 구현할 도구 (Tools)

| 도구명 | 설명 | 파라미터 |
|--------|------|----------|
| `get_issue` | 이슈 상세 조회 | issueKey (string) |
| `get_comments` | 이슈 댓글 조회 | issueKey (string) |
| `add_comment` | 이슈에 댓글 추가 | issueKey (string), body (string) |
| `search_issues` | JQL로 이슈 검색 | jql (string), maxResults (int, default=20) |
| `get_transitions` | 이슈 상태 변경 가능 목록 | issueKey (string) |
| `transition_issue` | 이슈 상태 변경 | issueKey (string), transitionId (string) |

### 환경 변수

```
JIRA_BASE_URL=https://{domain}.atlassian.net
JIRA_EMAIL=<email>
JIRA_API_TOKEN=<API 토큰>
```

### Claude Code 연동 설정

서버를 먼저 실행(`python -m mcp_gateway`)한 뒤, settings.json에 URL만 등록:

```json
{
  "mcpServers": {
    "gateway": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

## 댓글 파싱 참고

JIRA API v3의 댓글 body는 ADF(Atlassian Document Format) 형식이다. 텍스트 추출 시 재귀적으로 파싱 필요:

```
주요 노드 타입:
- type: "text" → node.text 추출
- type: "mention" → node.attrs.text 추출 (예: @사용자명)
- type: "hardBreak" → 줄바꿈(\n)
- content: [] → 자식 노드 재귀 탐색
```

## 참고 링크

- JIRA REST API v3 문서: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Claude Code MCP 설정: https://docs.anthropic.com/en/docs/claude-code/mcp
