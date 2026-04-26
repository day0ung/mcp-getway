# Notion MCP 서버 구축 가이드

## 배경

- Notion REST API를 직접 호출하는 모듈을 Gateway에 통합
- Jira / Confluence / GitLab과 동일 패턴 (`src/mcp_gateway/notion/`)

## Notion 접속 정보

| 항목 | 값 |
|------|------|
| API Base URL | `https://api.notion.com` |
| 인증 방식 | Bearer Token (Internal Integration Token) |
| 필수 헤더 | `Authorization: Bearer <token>`<br>`Notion-Version: 2022-06-28` |

## 인증 방식

Notion API는 두 가지 방식이 있다.

| 방식 | 용도 | Gateway 채택 |
|------|------|------|
| **Internal Integration** | 사내/개인 워크스페이스 전용. 토큰 한 번 발급 후 헤더에 박아넣으면 끝 | ✅ |
| Public OAuth | 외부 사용자에게 배포할 SaaS. OAuth 2.0 dance 필요 | ✗ |

Internal Integration은 토큰만 발급하면 되지만, **사용할 페이지/DB에 직접 Connections로 연결**해야 권한이 생긴다는 게 핵심 차이점이다 (Jira·Confluence는 토큰만으로 사이트 전체 접근 가능).

## 셋업 (1회)

### 1. Internal Integration 생성 → 토큰 발급

1. https://www.notion.so/profile/integrations 접속
2. **+ New integration** 클릭
3. 이름 입력 (예: `mcp-gateway`), 워크스페이스 선택
4. **Type** = `Internal`
5. **Capabilities** 체크
   - Read content
   - Update content
   - Insert content
   - (선택) Read user information
6. 저장 후 **Internal Integration Secret** 복사 (`secret_...`로 시작)

### 2. `.env` 등록

```env
# .env
NOTION_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# (선택) 기본값 사용 권장
# NOTION_VERSION=2022-06-28
```

### 3. 페이지/DB에 Integration 연결 (필수)

Internal Integration은 Connections를 통해 명시적으로 연결된 페이지에만 접근할 수 있다.

1. Notion에서 사용할 **페이지 또는 데이터베이스** 열기
2. 우상단 `•••` 메뉴 클릭
3. **Connections** → **Connect to** → 방금 만든 integration 선택
4. (자식 페이지·DB는 부모에서 한 번 연결하면 자동 상속)

> **권한 없음 (`object_not_found`) 에러가 뜨는 거의 모든 경우는 이 연결을 안 한 것이다.**

### 4. 검증

`.cache_pages/_notion_smoke.py` 같은 스모크 스크립트 또는 직접 Gateway 재시작 후 `search_notion` 호출.

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe .cache_pages/_notion_smoke.py
# 기대: [search] N건 (N>0)
```

## 사용 중인 Notion REST API 엔드포인트

| 메서드 | 경로 | Gateway 메서드 |
|---|---|---|
| `POST` | `/v1/search` | `NotionClient.search` |
| `GET` | `/v1/pages/{id}` | `NotionClient.get_page` |
| `POST` | `/v1/pages` | `NotionClient.create_page` |
| `PATCH` | `/v1/pages/{id}` | `NotionClient.update_page` |
| `GET` | `/v1/blocks/{id}/children` | `NotionClient.get_block_children` / `get_all_block_children` |
| `PATCH` | `/v1/blocks/{id}/children` | `NotionClient.append_blocks` |
| `GET` | `/v1/databases/{id}` | `NotionClient.get_database` |
| `POST` | `/v1/databases/{id}/query` | `NotionClient.query_database` |

## 등록된 MCP 도구

| 도구 | 용도 |
|---|---|
| `search_notion` | 워크스페이스 키워드 검색 (page/database 필터) |
| `get_notion_page` | 페이지 properties + 본문 블록을 markdown으로 변환 |
| `create_notion_page` | 페이지/DB row 생성 (간이 markdown 본문 지원) |
| `update_notion_page` | properties 변경 또는 archive 토글 |
| `append_notion_blocks` | 페이지 본문에 블록 추가 |
| `get_notion_database` | DB 메타데이터 + 컬럼 스키마 조회 |
| `query_notion_database` | DB row 조회 (filter/sort) |

## ID 정규화

Notion API는 dash 포함 UUID(`abc12345-...`)를 요구하지만, 사용자가 흔히 가져오는 형태는 다양하다. `NotionClient.normalize_id()`가 다음을 모두 받는다.

- `https://www.notion.so/Spring-Cloud-Config-02149f9bcb404ffdae3c36880090f18c` (URL)
- `02149f9bcb404ffdae3c36880090f18c` (dash 없는 32자)
- `02149f9b-cb40-4ffd-ae3c-36880090f18c` (정규형)

따라서 도구 인자에 페이지 URL을 그대로 던져도 동작한다.

## 본문 변환 (블록 → markdown)

`NotionBlock.to_markdown()`이 다음 블록 타입을 markdown으로 변환한다.

| Notion 블록 | Markdown |
|---|---|
| `paragraph` | 일반 텍스트 |
| `heading_1` / `2` / `3` | `#` / `##` / `###` |
| `bulleted_list_item` | `- item` |
| `numbered_list_item` | `1. item` |
| `to_do` | `- [x] / - [ ]` |
| `quote` | `> item` |
| `code` | ` ```lang ... ``` ` |
| `divider` | `---` |
| `callout` | `<emoji> text` |
| 기타 | `[type] text` 폴백 |

복잡한 변환(중첩 리스트, 인라인 mention 등)은 의도적으로 단순화. 필요해지면 그때 확장.

## 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| `search` 결과가 0건 | integration이 어떤 페이지에도 연결되지 않음 → Connections 추가 |
| `object_not_found` (404) | 해당 페이지/DB에 integration 미연결 또는 ID 오타 |
| `unauthorized` (401) | 토큰 오타 또는 토큰 만료 |
| `validation_error` (400) on create/update | properties JSON이 DB 스키마와 안 맞음. `get_notion_database`로 컬럼 타입 먼저 확인 |
| 한글이 콘솔에서 깨짐 | `PYTHONIOENCODING=utf-8` 환경변수 설정 |