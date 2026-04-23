# Claude Code는 이 설정을 어떻게 읽는가

`mcpServers` / `gateway` 같은 단어가 어디서 왔고 어떻게 엮이는지 헷갈릴 때 참고.

## 구조 해부

```json
{
  "mcpServers": {   ← ① Claude Code가 정해둔 고정 키. 바꾸면 안 됨.
    "gateway": {    ← ② 사용자가 임의로 지은 이름(라벨). 뭐든 됨.
      "url": "http://localhost:8000/sse"
    }
  }
}
```

- **`mcpServers`** 는 Claude Code의 설정 스펙으로 정해진 이름. 반드시 이대로.
- **`gateway`** 는 당신이 지은 이름. `d-lab`, `my-stuff` 뭐든 가능.
- MCP 서버 코드 자체(`server.py`의 `FastMCP("MCP Gateway", ...)`)와는 **무관**. 서버는 자기가 어떤 라벨로 등록됐는지 모른다.

## Claude Code 기동 시 동작 순서

```
[1] Claude Code 실행
      │
[2] 다음 파일을 찾아 "mcpServers" 섹션을 모두 수집
      ├─ 프로젝트 루트/.mcp.json                (이 레포에 해당)
      ├─ 프로젝트 루트/.claude/settings.json    (옵션 B)
      └─ ~/.claude/settings.json               (옵션 A, Windows: C:\Users\USER\.claude\)
      │
[3] 각 항목에 대해 연결
      │   "url"  → HTTP SSE로 접속 (http://localhost:8000/sse)
      │   "command" → 그 명령을 서브프로세스로 띄우고 stdio로 통신
      │
[4] 서버에 "tools/list" 요청 → 서버가 툴 목록 반환
      예: [get_issue, list_projects, get_merge_request, ...]
      │
[5] Claude는 툴 이름에 서버 라벨을 prefix로 붙여서 노출
      "gateway" + get_issue       → mcp__gateway__get_issue
      "gateway" + list_projects   → mcp__gateway__list_projects
```

## 라벨을 바꾸면

`"gateway"` 를 `"dayoung"` 로 바꾸면 툴 이름이 `mcp__dayoung__get_issue` 로 바뀐다. 서버 동작은 같음. 다만 **이전 대화에서 Claude가 기억하던 툴 이름이 안 맞게 되므로** 보통 한 번 정하면 유지한다.

## 전송 방식 차이

| 방식 | 설정 형태 | 서버가 떠있어야? | 용도 |
|---|---|---|---|
| **SSE** | `"url": "http://localhost:8000/sse"` | ✅ 미리 떠있어야 함 | 한 서버를 여러 프로젝트가 공유 |
| **stdio** | `"command": "...exe", "args": [...]` | ❌ Claude가 자동으로 띄움 | 이 레포에서 개발/디버깅용 |

같은 `mcp-gateway` 바이너리가 CLI 플래그(`--transport`)에 따라 두 모드를 모두 지원.

## 설정 반영 타이밍

- 설정 파일 수정 → **Claude Code 재시작 필수** (완전 종료 후 재실행).
- 서버 코드만 고친 경우도 서버 재기동 + Claude Code 재시작 (새 툴 목록을 다시 읽어야 함).
- `.env` 값만 바꾸면 **서버 재기동만** 하면 됨 (Claude 재시작 불필요, 툴 목록은 그대로이므로).