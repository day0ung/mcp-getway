from __future__ import annotations

from typing import Any


class ConfluencePage:
    """Confluence 페이지 응답(v2)을 정리된 dict로 변환."""

    @staticmethod
    def from_raw(data: dict[str, Any]) -> dict[str, Any]:
        body = data.get("body") or {}
        storage = body.get("storage") or body.get("atlas_doc_format") or {}
        version = data.get("version") or {}

        return {
            "id": data.get("id", ""),
            "title": data.get("title", ""),
            "status": data.get("status", ""),
            "space_id": data.get("spaceId", ""),
            "parent_id": data.get("parentId", ""),
            "author_id": data.get("authorId", ""),
            "created_at": data.get("createdAt", ""),
            "version": version.get("number", 0),
            "body_representation": storage.get("representation", ""),
            "body": storage.get("value", ""),
        }


class ConfluenceDatabase:
    """Confluence 데이터베이스 응답(v2)을 정리된 dict로 변환."""

    @staticmethod
    def from_raw(data: dict[str, Any]) -> dict[str, Any]:
        version = data.get("version") or {}
        return {
            "id": data.get("id", ""),
            "title": data.get("title", ""),
            "status": data.get("status", ""),
            "space_id": data.get("spaceId", ""),
            "parent_id": data.get("parentId", ""),
            "author_id": data.get("authorId", ""),
            "created_at": data.get("createdAt", ""),
            "version": version.get("number", 0),
        }


class ConfluenceSearchHit:
    """Confluence CQL 검색 결과 항목을 정리된 dict로 변환."""

    @staticmethod
    def from_raw(data: dict[str, Any]) -> dict[str, Any]:
        content = data.get("content") or {}
        space = data.get("resultGlobalContainer") or {}
        return {
            "id": content.get("id", ""),
            "type": content.get("type", ""),
            "title": data.get("title") or content.get("title", ""),
            "space": space.get("title", ""),
            "url": data.get("url", ""),
            "last_modified": data.get("lastModified", ""),
            "excerpt": data.get("excerpt", ""),
        }