from __future__ import annotations

from typing import Any


class GitLabProject:
    @staticmethod
    def summary(data: dict[str, Any]) -> dict[str, Any]:
        namespace = data.get("namespace") or {}
        return {
            "id": data.get("id"),
            "path_with_namespace": data.get("path_with_namespace", ""),
            "name": data.get("name", ""),
            "default_branch": data.get("default_branch", ""),
            "visibility": data.get("visibility", ""),
            "web_url": data.get("web_url", ""),
            "namespace": namespace.get("full_path", ""),
            "last_activity_at": data.get("last_activity_at", ""),
        }


class GitLabMergeRequest:
    @staticmethod
    def summary(data: dict[str, Any]) -> dict[str, Any]:
        author = data.get("author") or {}
        assignee = data.get("assignee") or {}
        return {
            "iid": data.get("iid"),
            "title": data.get("title", ""),
            "state": data.get("state", ""),
            "draft": data.get("draft", False),
            "source_branch": data.get("source_branch", ""),
            "target_branch": data.get("target_branch", ""),
            "author": author.get("username", ""),
            "assignee": assignee.get("username", "") if assignee else "",
            "web_url": data.get("web_url", ""),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "merge_status": data.get("detailed_merge_status") or data.get("merge_status", ""),
            "has_conflicts": data.get("has_conflicts", False),
        }


class GitLabCommit:
    @staticmethod
    def summary(data: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": data.get("id", ""),
            "short_id": data.get("short_id", ""),
            "title": data.get("title", ""),
            "author_name": data.get("author_name", ""),
            "authored_date": data.get("authored_date", ""),
            "web_url": data.get("web_url", ""),
        }


class GitLabBranch:
    @staticmethod
    def summary(data: dict[str, Any]) -> dict[str, Any]:
        commit = data.get("commit") or {}
        return {
            "name": data.get("name", ""),
            "default": data.get("default", False),
            "protected": data.get("protected", False),
            "merged": data.get("merged", False),
            "web_url": data.get("web_url", ""),
            "commit": {
                "id": commit.get("id", ""),
                "short_id": commit.get("short_id", ""),
                "title": commit.get("title", ""),
                "authored_date": commit.get("authored_date", ""),
            },
        }


class GitLabDiff:
    """GitLab Merge Request diff 파일 항목."""

    @staticmethod
    def file_path(data: dict[str, Any]) -> str:
        """diff 엔트리에서 '사용자에게 보여줄 경로' 하나만 뽑는다."""
        return data.get("new_path") or data.get("old_path") or ""

    @staticmethod
    def changed_file_summary(data: dict[str, Any]) -> dict[str, Any]:
        """list_merge_request_changed_files 용 — diff 본문은 빼고 메타만."""
        return {
            "old_path": data.get("old_path", ""),
            "new_path": data.get("new_path", ""),
            "new_file": data.get("new_file", False),
            "renamed_file": data.get("renamed_file", False),
            "deleted_file": data.get("deleted_file", False),
        }