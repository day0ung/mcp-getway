from __future__ import annotations

from typing import Any


def _plain_text(rich_text: list[dict[str, Any]] | None) -> str:
    if not rich_text:
        return ""
    return "".join(seg.get("plain_text", "") for seg in rich_text)


def _title_from_properties(properties: dict[str, Any]) -> str:
    for prop in properties.values():
        if prop.get("type") == "title":
            return _plain_text(prop.get("title"))
    return ""


def _summarize_property(prop: dict[str, Any]) -> Any:
    """속성 객체에서 사람이 읽기 좋은 값 한 가지만 뽑아낸다."""
    ptype = prop.get("type")
    value = prop.get(ptype) if ptype else None
    if value is None:
        return None
    if ptype in {"title", "rich_text"}:
        return _plain_text(value)
    if ptype == "select":
        return (value or {}).get("name")
    if ptype == "multi_select":
        return [item.get("name") for item in value]
    if ptype == "status":
        return (value or {}).get("name")
    if ptype == "people":
        return [item.get("name") or item.get("id") for item in value]
    if ptype == "date":
        if not value:
            return None
        return {"start": value.get("start"), "end": value.get("end")}
    if ptype == "checkbox":
        return bool(value)
    if ptype in {"number", "url", "email", "phone_number"}:
        return value
    if ptype == "relation":
        return [item.get("id") for item in value]
    if ptype == "files":
        return [item.get("name") for item in value]
    if ptype == "formula":
        ftype = value.get("type")
        return value.get(ftype) if ftype else None
    return value


class NotionPage:
    """Notion 페이지 응답을 정리된 dict로 변환."""

    @staticmethod
    def from_raw(data: dict[str, Any]) -> dict[str, Any]:
        properties = data.get("properties") or {}
        parent = data.get("parent") or {}
        return {
            "id": data.get("id", ""),
            "title": _title_from_properties(properties),
            "url": data.get("url", ""),
            "archived": data.get("archived", False),
            "created_time": data.get("created_time", ""),
            "last_edited_time": data.get("last_edited_time", ""),
            "parent": parent,
            "properties": {k: _summarize_property(v) for k, v in properties.items()},
        }


class NotionSearchHit:
    """Notion 검색 결과 항목을 정리된 dict로 변환."""

    @staticmethod
    def from_raw(data: dict[str, Any]) -> dict[str, Any]:
        obj = data.get("object", "")
        title = ""
        if obj == "page":
            title = _title_from_properties(data.get("properties") or {})
        elif obj == "database":
            title = _plain_text(data.get("title"))
        return {
            "object": obj,
            "id": data.get("id", ""),
            "title": title,
            "url": data.get("url", ""),
            "last_edited_time": data.get("last_edited_time", ""),
        }


class NotionDatabase:
    """Notion 데이터베이스 메타데이터를 정리된 dict로 변환."""

    @staticmethod
    def from_raw(data: dict[str, Any]) -> dict[str, Any]:
        properties = data.get("properties") or {}
        schema = {
            name: {"type": prop.get("type"), "id": prop.get("id")}
            for name, prop in properties.items()
        }
        return {
            "id": data.get("id", ""),
            "title": _plain_text(data.get("title")),
            "description": _plain_text(data.get("description")),
            "url": data.get("url", ""),
            "created_time": data.get("created_time", ""),
            "last_edited_time": data.get("last_edited_time", ""),
            "schema": schema,
        }


class NotionBlock:
    """Notion 블록을 markdown-friendly 텍스트로 요약."""

    @staticmethod
    def to_markdown(blocks: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for block in blocks:
            lines.append(NotionBlock._block_to_md(block))
        return "\n".join(line for line in lines if line is not None)

    @staticmethod
    def _block_to_md(block: dict[str, Any]) -> str:
        btype = block.get("type", "")
        body = block.get(btype) or {}
        text = _plain_text(body.get("rich_text"))
        if btype == "paragraph":
            return text
        if btype == "heading_1":
            return f"# {text}"
        if btype == "heading_2":
            return f"## {text}"
        if btype == "heading_3":
            return f"### {text}"
        if btype == "bulleted_list_item":
            return f"- {text}"
        if btype == "numbered_list_item":
            return f"1. {text}"
        if btype == "to_do":
            checked = body.get("checked", False)
            return f"- [{'x' if checked else ' '}] {text}"
        if btype == "quote":
            return f"> {text}"
        if btype == "code":
            lang = body.get("language", "")
            return f"```{lang}\n{text}\n```"
        if btype == "divider":
            return "---"
        if btype == "callout":
            icon = (body.get("icon") or {}).get("emoji", "")
            return f"{icon} {text}".strip()
        if btype == "toggle":
            return f"<details><summary>{text}</summary></details>"
        if btype == "child_page":
            return f"[child page] {body.get('title', '')}"
        if btype == "child_database":
            return f"[child database] {body.get('title', '')}"
        return f"[{btype}] {text}"