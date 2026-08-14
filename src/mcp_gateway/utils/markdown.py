"""마크다운 → ADF 변환 헬퍼.

Jira API v3의 description/comment body는 ADF(Atlassian Document Format)를
요구한다. 사용자가 본문에 마크다운 표나 인라인 서식을 넣어도 기존
text_to_adf 는 각 줄을 그대로 텍스트로 넣어버려 `|` 파이프가 리터럴로
보이고 표가 렌더링되지 않았다.

이 모듈은 마크다운 표 블록과 인라인 서식(인라인 코드/볼드)을 감지해
ADF 노드로 변환한다. 표가 아닌 일반 텍스트는 건드리지 않는다.
"""

from __future__ import annotations

import re
from typing import Any

# 인라인 코드(`code`) 또는 볼드(**bold**) 토큰
_INLINE_RE = re.compile(r"(`[^`]+`|\*\*[^*]+\*\*)")

# 표 구분선 셀: 선택적 정렬 콜론 + 하이픈 (예: ---, :---, :--:, ---:)
_SEP_CELL_RE = re.compile(r"^:?-+:?$")


def parse_inline(text: str) -> list[dict[str, Any]]:
    """인라인 서식을 ADF text 노드 리스트로 변환한다.

    지원: `인라인코드` → code mark, **볼드** → strong mark.
    나머지는 순수 text 노드. 빈 문자열 토큰은 버린다.
    """
    nodes: list[dict[str, Any]] = []
    for part in _INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("`") and part.endswith("`") and len(part) >= 2:
            nodes.append(
                {"type": "text", "text": part[1:-1], "marks": [{"type": "code"}]}
            )
        elif part.startswith("**") and part.endswith("**") and len(part) >= 4:
            nodes.append(
                {"type": "text", "text": part[2:-2], "marks": [{"type": "strong"}]}
            )
        else:
            nodes.append({"type": "text", "text": part})
    return nodes


def _split_row(line: str) -> list[str]:
    """표 한 줄을 셀 리스트로 분리한다.

    이스케이프된 `\\|` 는 리터럴 파이프로 복원한다.
    양 끝의 파이프로 인한 빈 셀은 제거한다.
    """
    # 이스케이프 파이프를 임시 치환 후 분리
    placeholder = "\x00"
    tmp = line.replace("\\|", placeholder)
    cells = tmp.split("|")
    # 양 끝 파이프로 생긴 빈 셀 제거
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.replace(placeholder, "|").strip() for c in cells]


def _is_separator_row(line: str) -> bool:
    """`| --- | --- |` 형태의 구분선 여부."""
    stripped = line.strip()
    if "|" not in stripped or "-" not in stripped:
        return False
    cells = _split_row(stripped)
    if not cells:
        return False
    return all(_SEP_CELL_RE.match(c) for c in cells)


def _looks_like_table_row(line: str) -> bool:
    return "|" in line and not _is_separator_row(line)


def split_blocks(text: str) -> list[tuple]:
    """텍스트를 표 블록과 일반 텍스트 블록으로 순서대로 분리한다.

    반환 요소:
      ("text", "...원본 텍스트...")
      ("table", [헤더셀...], [[행셀...], ...])

    표 인정 조건: 헤더 행(파이프 포함) 다음 줄이 구분선(| --- |)일 것.
    구분선이 없으면 표로 취급하지 않는다(오탐 방지).
    """
    lines = text.split("\n")
    blocks: list[tuple] = []
    text_buf: list[str] = []
    i = 0
    n = len(lines)

    def flush_text() -> None:
        if text_buf:
            blocks.append(("text", "\n".join(text_buf)))
            text_buf.clear()

    while i < n:
        line = lines[i]
        is_header = (
            _looks_like_table_row(line)
            and i + 1 < n
            and _is_separator_row(lines[i + 1])
        )
        if is_header:
            headers = _split_row(line)
            rows: list[list[str]] = []
            j = i + 2
            while j < n and _looks_like_table_row(lines[j]):
                cells = _split_row(lines[j])
                # 헤더 열 개수에 맞춰 패딩/절단
                if len(cells) < len(headers):
                    cells = cells + [""] * (len(headers) - len(cells))
                elif len(cells) > len(headers):
                    cells = cells[: len(headers)]
                rows.append(cells)
                j += 1
            flush_text()
            blocks.append(("table", headers, rows))
            i = j
        else:
            text_buf.append(line)
            i += 1

    flush_text()
    return blocks


def _cell_paragraph(text: str) -> dict[str, Any]:
    """셀 내용을 담은 paragraph 노드. 빈 셀은 content 없는 paragraph."""
    nodes = parse_inline(text) if text else []
    if nodes:
        return {"type": "paragraph", "content": nodes}
    return {"type": "paragraph"}


def table_to_adf(headers: list[str], rows: list[list[str]]) -> dict[str, Any]:
    """표 데이터를 ADF table 노드로 변환한다."""
    content: list[dict[str, Any]] = []

    header_cells = [
        {"type": "tableHeader", "attrs": {}, "content": [_cell_paragraph(h)]}
        for h in headers
    ]
    content.append({"type": "tableRow", "content": header_cells})

    for row in rows:
        cells = [
            {"type": "tableCell", "attrs": {}, "content": [_cell_paragraph(c)]}
            for c in row
        ]
        content.append({"type": "tableRow", "content": cells})

    return {
        "type": "table",
        "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
        "content": content,
    }