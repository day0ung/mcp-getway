"""Atlassian Document Format (ADF) 파서.

JIRA API v3의 댓글/설명 body는 ADF 형식이다.
이 모듈은 ADF ↔ 텍스트 변환을 담당한다.
"""

from __future__ import annotations

from typing import Any


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


def text_to_adf(text: str) -> dict[str, Any]:
    """텍스트를 ADF 형식으로 변환한다 (댓글 작성용)."""
    paragraphs = text.split("\n\n") if "\n\n" in text else [text]

    content = []
    for para in paragraphs:
        lines = para.split("\n")
        para_content: list[dict[str, Any]] = []
        for i, line in enumerate(lines):
            if line:
                para_content.append({"type": "text", "text": line})
            if i < len(lines) - 1:
                para_content.append({"type": "hardBreak"})

        if para_content:
            content.append({"type": "paragraph", "content": para_content})

    return {
        "type": "doc",
        "version": 1,
        "content": content,
    }
