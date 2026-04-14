from __future__ import annotations

from typing import Any

from ..utils.adf import parse_adf


class JiraIssue:
    """JIRA 이슈 응답을 정리된 dict로 변환."""

    @staticmethod
    def from_raw(data: dict[str, Any]) -> dict[str, Any]:
        fields = data.get("fields", {})
        assignee = fields.get("assignee")
        reporter = fields.get("reporter")
        status = fields.get("status")
        priority = fields.get("priority")
        issuetype = fields.get("issuetype")

        description_adf = fields.get("description")
        description = parse_adf(description_adf) if description_adf else ""

        return {
            "key": data.get("key", ""),
            "summary": fields.get("summary", ""),
            "status": status.get("name", "") if status else "",
            "assignee": assignee.get("displayName", "") if assignee else "미배정",
            "reporter": reporter.get("displayName", "") if reporter else "",
            "priority": priority.get("name", "") if priority else "",
            "issuetype": issuetype.get("name", "") if issuetype else "",
            "created": fields.get("created", ""),
            "updated": fields.get("updated", ""),
            "description": description,
        }


class JiraComment:
    """JIRA 댓글 응답을 정리된 dict로 변환."""

    @staticmethod
    def from_raw(data: dict[str, Any]) -> dict[str, Any]:
        author = data.get("author", {})
        body_adf = data.get("body")
        body = parse_adf(body_adf) if body_adf else ""

        return {
            "id": data.get("id", ""),
            "author": author.get("displayName", ""),
            "body": body,
            "created": data.get("created", ""),
            "updated": data.get("updated", ""),
        }


class JiraTransition:
    """JIRA 트랜지션 응답을 정리된 dict로 변환."""

    @staticmethod
    def from_raw(data: dict[str, Any]) -> dict[str, Any]:
        to_status = data.get("to", {})
        return {
            "id": data.get("id", ""),
            "name": data.get("name", ""),
            "to": to_status.get("name", ""),
        }
