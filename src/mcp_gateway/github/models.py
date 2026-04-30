from __future__ import annotations

from typing import Any


class GitHubRepo:
    @staticmethod
    def summary(data: dict[str, Any]) -> dict[str, Any]:
        owner = data.get("owner") or {}
        return {
            "id": data.get("id"),
            "full_name": data.get("full_name", ""),
            "name": data.get("name", ""),
            "owner": owner.get("login", ""),
            "default_branch": data.get("default_branch", ""),
            "visibility": data.get("visibility", ""),
            "private": data.get("private", False),
            "html_url": data.get("html_url", ""),
            "description": data.get("description", ""),
            "updated_at": data.get("updated_at", ""),
        }


class GitHubPullRequest:
    @staticmethod
    def summary(data: dict[str, Any]) -> dict[str, Any]:
        user = data.get("user") or {}
        assignee = data.get("assignee") or {}
        head = data.get("head") or {}
        base = data.get("base") or {}
        return {
            "number": data.get("number"),
            "title": data.get("title", ""),
            "state": data.get("state", ""),
            "draft": data.get("draft", False),
            "head": head.get("ref", ""),
            "base": base.get("ref", ""),
            "author": user.get("login", ""),
            "assignee": assignee.get("login", "") if assignee else "",
            "html_url": data.get("html_url", ""),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "merged": data.get("merged", False),
            "mergeable": data.get("mergeable"),
        }


class GitHubCommit:
    @staticmethod
    def summary(data: dict[str, Any]) -> dict[str, Any]:
        commit = data.get("commit") or {}
        author = commit.get("author") or {}
        return {
            "sha": data.get("sha", ""),
            "short_sha": (data.get("sha") or "")[:7],
            "message": commit.get("message", "").split("\n")[0],
            "author": author.get("name", ""),
            "date": author.get("date", ""),
            "html_url": data.get("html_url", ""),
        }


class GitHubBranch:
    @staticmethod
    def summary(data: dict[str, Any]) -> dict[str, Any]:
        commit = data.get("commit") or {}
        return {
            "name": data.get("name", ""),
            "protected": data.get("protected", False),
            "commit": {
                "sha": commit.get("sha", ""),
                "url": commit.get("url", ""),
            },
        }