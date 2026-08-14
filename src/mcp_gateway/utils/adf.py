"""Atlassian Document Format (ADF) 파서.

JIRA API v3의 댓글/설명 body는 ADF 형식이다.
이 모듈은 ADF ↔ 텍스트 변환을 담당한다.
"""

from __future__ import annotations

from typing import Any

from .markdown import parse_inline, split_blocks, table_to_adf


def parse_adf(node: dict[str, Any] | None) -> str:
    """ADF 노드를 재귀적으로 파싱하여 텍스트로 변환한다."""
    if node is None:
        return ""

    node_type = node.get("type", "")

    if node_type == "text":
        return node.get("text", "")

    if node_type == "mention":
        attrs = node.get("attrs", {})
        return attrs.get("text", "")

    if node_type == "hardBreak":
        return "\n"

    if node_type == "emoji":
        attrs = node.get("attrs", {})
        return attrs.get("shortName", "")

    # 자식 노드 재귀 탐색
    parts: list[str] = []
    for child in node.get("content", []):
        parts.append(parse_adf(child))

    text = "".join(parts)

    # 블록 노드는 줄바꿈 추가
    if node_type in ("paragraph", "heading", "bulletList", "orderedList", "listItem"):
        text = text.rstrip() + "\n"

    return text


def _text_to_paragraphs(text: str) -> list[dict[str, Any]]:
    """일반 텍스트를 paragraph 노드 리스트로 변환한다.

    빈 줄(\\n\\n)로 문단을 나누고, 문단 내 줄바꿈은 hardBreak 로 잇는다.
    각 줄은 인라인 서식(코드/볼드)을 파싱한다.
    """
    if not text.strip():
        return []

    paragraphs = text.split("\n\n") if "\n\n" in text else [text]

    result: list[dict[str, Any]] = []
    for para in paragraphs:
        lines = para.split("\n")
        para_content: list[dict[str, Any]] = []
        for i, line in enumerate(lines):
            if line:
                para_content.extend(parse_inline(line))
            if i < len(lines) - 1:
                para_content.append({"type": "hardBreak"})

        if para_content:
            result.append({"type": "paragraph", "content": para_content})
    return result


def text_to_adf(text: str) -> dict[str, Any]:
    """텍스트를 ADF 형식으로 변환한다 (댓글/설명 작성용).

    마크다운 표(| h | h |\\n| --- | --- |\\n| a | b |)는 ADF table 노드로,
    인라인 코드(`code`)/볼드(**bold**)는 각 mark 로 변환한다.
    표가 아닌 텍스트의 기존 동작(문단 + hardBreak)은 유지된다.
    """
    content: list[dict[str, Any]] = []
    for block in split_blocks(text):
        if block[0] == "table":
            content.append(table_to_adf(block[1], block[2]))
        else:
            content.extend(_text_to_paragraphs(block[1]))

    if not content:
        content = [{"type": "paragraph"}]

    return {
        "type": "doc",
        "version": 1,
        "content": content,
    }
