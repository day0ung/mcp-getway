"""GitHub MCP 도구 정의."""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from ..github.models import (
    GitHubBranch,
    GitHubCommit,
    GitHubPullRequest,
    GitHubRepo,
)

logger = logging.getLogger("mcp_gateway.tools.github")


def _client(ctx: Context):
    return ctx.request_context.lifespan_context["github_client"]


def register_tools(mcp: FastMCP) -> None:
    """MCP 서버에 GitHub 도구들을 등록한다."""

    # ── Repositories ────────────────────────────────────────────────────

    @mcp.tool()
    async def gh_list_repos(
        ctx: Context,
        search: Annotated[str, Field(description="저장소 이름/설명 검색어 (선택)", default="")] = "",
        per_page: Annotated[int, Field(description="최대 결과 수", default=20)] = 20,
    ) -> str:
        """GitHub 저장소 목록을 조회한다. search 없으면 내 저장소, 있으면 전체 검색."""
        logger.info("gh_list_repos: search=%s", search)
        raw = await _client(ctx).list_repos(search=search or None, per_page=per_page)
        return json.dumps([GitHubRepo.summary(r) for r in raw], ensure_ascii=False)

    @mcp.tool()
    async def gh_get_repo(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
    ) -> str:
        """GitHub 저장소 상세 정보를 조회한다."""
        logger.info("gh_get_repo: %s", owner_repo)
        raw = await _client(ctx).get_repo(owner_repo)
        return json.dumps(GitHubRepo.summary(raw), ensure_ascii=False)

    @mcp.tool()
    async def gh_get_file_contents(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        file_path: Annotated[str, Field(description="파일 경로 (예: src/app.py)")],
        ref: Annotated[str, Field(description="브랜치/태그/SHA (기본: HEAD)", default="HEAD")] = "HEAD",
    ) -> str:
        """GitHub 저장소에서 파일 내용을 조회한다. 텍스트 파일이면 decoded_content 필드에 복호화된 내용을 담는다."""
        logger.info("gh_get_file_contents: %s@%s %s", owner_repo, ref, file_path)
        raw = await _client(ctx).get_file_contents(owner_repo, file_path, ref=ref)
        out: dict[str, Any] = {
            "name": raw.get("name", ""),
            "path": raw.get("path", ""),
            "sha": raw.get("sha", ""),
            "size": raw.get("size", 0),
            "encoding": raw.get("encoding", ""),
            "html_url": raw.get("html_url", ""),
        }
        if raw.get("encoding") == "base64" and raw.get("content"):
            content_bytes = raw["content"].replace("\n", "")
            try:
                out["decoded_content"] = base64.b64decode(content_bytes).decode("utf-8")
            except UnicodeDecodeError:
                out["decoded_content"] = None
                out["note"] = "바이너리 파일로 판단되어 decoded_content 를 제공하지 않음"
        else:
            out["content"] = raw.get("content", "")
        return json.dumps(out, ensure_ascii=False)

    @mcp.tool()
    async def gh_get_repository_tree(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        path: Annotated[str, Field(description="디렉토리 경로 (선택, 기본은 루트)", default="")] = "",
        ref: Annotated[str, Field(description="브랜치/태그/SHA (기본: HEAD)", default="HEAD")] = "HEAD",
        per_page: Annotated[int, Field(description="최대 결과 수", default=100)] = 100,
    ) -> str:
        """GitHub 저장소의 디렉토리 목록을 조회한다."""
        logger.info("gh_get_repository_tree: %s path=%s ref=%s", owner_repo, path, ref)
        raw = await _client(ctx).get_repository_tree(owner_repo, path=path, ref=ref, per_page=per_page)
        simplified = [
            {"name": item.get("name", ""), "path": item.get("path", ""), "type": item.get("type", ""), "size": item.get("size")}
            for item in raw
        ]
        return json.dumps(simplified, ensure_ascii=False)

    @mcp.tool()
    async def gh_list_commits(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        sha: Annotated[str, Field(description="브랜치/태그/SHA (선택)", default="")] = "",
        since: Annotated[str, Field(description="ISO 8601 날짜 이후 (선택, 예: 2026-01-01T00:00:00Z)", default="")] = "",
        until: Annotated[str, Field(description="ISO 8601 날짜 이전 (선택)", default="")] = "",
        per_page: Annotated[int, Field(description="최대 결과 수", default=20)] = 20,
    ) -> str:
        """GitHub 저장소의 커밋 이력을 조회한다."""
        logger.info("gh_list_commits: %s sha=%s", owner_repo, sha)
        raw = await _client(ctx).list_commits(
            owner_repo, sha=sha or None, since=since or None, until=until or None, per_page=per_page
        )
        return json.dumps([GitHubCommit.summary(c) for c in raw], ensure_ascii=False)

    # ── Branches ─────────────────────────────────────────────────────────

    @mcp.tool()
    async def gh_list_branches(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        per_page: Annotated[int, Field(description="최대 결과 수", default=50)] = 50,
    ) -> str:
        """GitHub 저장소의 브랜치 목록을 조회한다."""
        logger.info("gh_list_branches: %s", owner_repo)
        raw = await _client(ctx).list_branches(owner_repo, per_page=per_page)
        return json.dumps([GitHubBranch.summary(b) for b in raw], ensure_ascii=False)

    @mcp.tool()
    async def gh_create_branch(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        branch: Annotated[str, Field(description="새로 만들 브랜치 이름")],
        sha: Annotated[str, Field(description="분기 기준이 될 커밋 SHA")],
    ) -> str:
        """GitHub 저장소에 새 브랜치를 생성한다."""
        logger.info("gh_create_branch: %s %s ← %s", owner_repo, branch, sha)
        raw = await _client(ctx).create_branch(owner_repo, branch=branch, sha=sha)
        ref_obj = raw.get("object") or {}
        return json.dumps(
            {"ref": raw.get("ref", ""), "sha": ref_obj.get("sha", ""), "url": raw.get("url", "")},
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def gh_get_branch_diffs(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        base: Annotated[str, Field(description="비교 기준 브랜치/SHA")],
        head: Annotated[str, Field(description="비교 대상 브랜치/SHA")],
    ) -> str:
        """두 브랜치/커밋 사이의 변경사항(diff)을 조회한다."""
        logger.info("gh_get_branch_diffs: %s %s…%s", owner_repo, base, head)
        raw = await _client(ctx).compare(owner_repo, base=base, head=head)
        return json.dumps(
            {
                "status": raw.get("status", ""),
                "ahead_by": raw.get("ahead_by", 0),
                "behind_by": raw.get("behind_by", 0),
                "total_commits": raw.get("total_commits", 0),
                "html_url": raw.get("html_url", ""),
                "files": [
                    {
                        "filename": f.get("filename", ""),
                        "status": f.get("status", ""),
                        "additions": f.get("additions", 0),
                        "deletions": f.get("deletions", 0),
                        "changes": f.get("changes", 0),
                    }
                    for f in raw.get("files", [])
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

    # ── Pull Requests ──────────────────────────────────────────────────

    @mcp.tool()
    async def gh_list_pull_requests(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        state: Annotated[str, Field(description="open / closed / all", default="open")] = "open",
        head: Annotated[str, Field(description="소스 브랜치 필터 (선택)", default="")] = "",
        base: Annotated[str, Field(description="타겟 브랜치 필터 (선택)", default="")] = "",
        per_page: Annotated[int, Field(description="최대 결과 수", default=20)] = 20,
    ) -> str:
        """GitHub PR 목록을 조회한다."""
        logger.info("gh_list_pull_requests: %s state=%s", owner_repo, state)
        raw = await _client(ctx).list_pull_requests(
            owner_repo, state=state, head=head or None, base=base or None, per_page=per_page
        )
        return json.dumps([GitHubPullRequest.summary(p) for p in raw], ensure_ascii=False)

    @mcp.tool()
    async def gh_get_pull_request(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        pull_number: Annotated[int, Field(description="PR 번호")],
    ) -> str:
        """GitHub PR 상세 정보를 조회한다."""
        logger.info("gh_get_pull_request: %s #%d", owner_repo, pull_number)
        raw = await _client(ctx).get_pull_request(owner_repo, pull_number)
        return json.dumps(GitHubPullRequest.summary(raw), ensure_ascii=False)

    @mcp.tool()
    async def gh_create_pull_request(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        head: Annotated[str, Field(description="소스 브랜치 (예: feature/my-feature)")],
        base: Annotated[str, Field(description="타겟 브랜치 (예: main)")],
        title: Annotated[str, Field(description="PR 제목")],
        body: Annotated[str, Field(description="PR 본문 (Markdown)", default="")] = "",
        draft: Annotated[bool, Field(description="Draft PR으로 생성", default=False)] = False,
    ) -> str:
        """새 GitHub PR을 생성한다."""
        logger.info("gh_create_pull_request: %s %s → %s title=%s", owner_repo, head, base, title)
        raw = await _client(ctx).create_pull_request(
            owner_repo, head=head, base=base, title=title, body=body, draft=draft
        )
        return json.dumps(GitHubPullRequest.summary(raw), ensure_ascii=False)

    @mcp.tool()
    async def gh_list_pr_changed_files(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        pull_number: Annotated[int, Field(description="PR 번호")],
        excluded_file_patterns: Annotated[
            str,
            Field(description="제외할 경로 정규식 패턴 (선택, 쉼표로 여러 개. 예: ^dist/,\\.lock$)", default=""),
        ] = "",
    ) -> str:
        """[리뷰 1단계] PR의 변경된 파일 목록을 조회한다 (diff 본문 없음)."""
        logger.info("gh_list_pr_changed_files: %s #%d", owner_repo, pull_number)
        raw = await _client(ctx).get_pull_request_files(owner_repo, pull_number, per_page=100)
        patterns = [p.strip() for p in excluded_file_patterns.split(",") if p.strip()]
        compiled = [re.compile(p) for p in patterns]
        results = []
        for f in raw:
            filename = f.get("filename", "")
            if any(c.search(filename) for c in compiled):
                continue
            results.append({
                "filename": filename,
                "status": f.get("status", ""),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "changes": f.get("changes", 0),
            })
        return json.dumps({"count": len(results), "files": results}, ensure_ascii=False)

    @mcp.tool()
    async def gh_get_pr_file_diff(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        pull_number: Annotated[int, Field(description="PR 번호")],
        file_paths: Annotated[str, Field(description="diff를 받을 파일 경로 (쉼표로 여러 개, 권장 3~5개)")],
    ) -> str:
        """[리뷰 2단계] 지정한 파일들의 diff 본문을 반환한다."""
        logger.info("gh_get_pr_file_diff: %s #%d files=%s", owner_repo, pull_number, file_paths)
        wanted = {p.strip() for p in file_paths.split(",") if p.strip()}
        raw = await _client(ctx).get_pull_request_files(owner_repo, pull_number, per_page=100)
        matched = [
            {
                "filename": f.get("filename", ""),
                "status": f.get("status", ""),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "changes": f.get("changes", 0),
                "patch": f.get("patch", ""),
            }
            for f in raw if f.get("filename") in wanted
        ]
        return json.dumps({"count": len(matched), "diffs": matched}, ensure_ascii=False)

    @mcp.tool()
    async def gh_merge_pull_request(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        pull_number: Annotated[int, Field(description="PR 번호")],
        commit_title: Annotated[str, Field(description="머지 커밋 제목 (선택)", default="")] = "",
        commit_message: Annotated[str, Field(description="머지 커밋 메시지 본문 (선택)", default="")] = "",
        merge_method: Annotated[str, Field(description="merge / squash / rebase", default="merge")] = "merge",
    ) -> str:
        """PR을 머지한다."""
        logger.info("gh_merge_pull_request: %s #%d method=%s", owner_repo, pull_number, merge_method)
        raw = await _client(ctx).merge_pull_request(
            owner_repo,
            pull_number,
            commit_title=commit_title or None,
            commit_message=commit_message or None,
            merge_method=merge_method,
        )
        return json.dumps({"sha": raw.get("sha", ""), "merged": raw.get("merged", False), "message": raw.get("message", "")}, ensure_ascii=False)

    # ── PR 리뷰 / 댓글 ────────────────────────────────────────────────

    @mcp.tool()
    async def gh_list_reviews(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        pull_number: Annotated[int, Field(description="PR 번호")],
    ) -> str:
        """PR의 리뷰 목록을 조회한다."""
        logger.info("gh_list_reviews: %s #%d", owner_repo, pull_number)
        raw = await _client(ctx).list_reviews(owner_repo, pull_number)
        return json.dumps(
            [
                {
                    "id": r.get("id"),
                    "user": (r.get("user") or {}).get("login", ""),
                    "state": r.get("state", ""),
                    "body": r.get("body", ""),
                    "submitted_at": r.get("submitted_at", ""),
                    "html_url": r.get("html_url", ""),
                }
                for r in raw
            ],
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def gh_create_review(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        pull_number: Annotated[int, Field(description="PR 번호")],
        event: Annotated[str, Field(description="APPROVE / REQUEST_CHANGES / COMMENT")] = "COMMENT",
        body: Annotated[str, Field(description="리뷰 본문 (Markdown)", default="")] = "",
    ) -> str:
        """PR 리뷰를 생성한다 (승인/변경 요청/코멘트)."""
        logger.info("gh_create_review: %s #%d event=%s", owner_repo, pull_number, event)
        raw = await _client(ctx).create_review(owner_repo, pull_number, event=event, body=body)
        return json.dumps(
            {"id": raw.get("id"), "state": raw.get("state", ""), "html_url": raw.get("html_url", "")},
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def gh_list_review_comments(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        pull_number: Annotated[int, Field(description="PR 번호")],
        per_page: Annotated[int, Field(description="최대 결과 수", default=50)] = 50,
    ) -> str:
        """PR의 인라인 코드 리뷰 댓글 목록을 조회한다."""
        logger.info("gh_list_review_comments: %s #%d", owner_repo, pull_number)
        raw = await _client(ctx).list_review_comments(owner_repo, pull_number, per_page=per_page)
        return json.dumps(
            [
                {
                    "id": c.get("id"),
                    "user": (c.get("user") or {}).get("login", ""),
                    "path": c.get("path", ""),
                    "line": c.get("line"),
                    "body": c.get("body", ""),
                    "created_at": c.get("created_at", ""),
                    "html_url": c.get("html_url", ""),
                }
                for c in raw
            ],
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def gh_create_review_comment(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        pull_number: Annotated[int, Field(description="PR 번호")],
        body: Annotated[str, Field(description="댓글 본문 (Markdown)")],
        commit_id: Annotated[str, Field(description="댓글을 달 커밋 SHA")],
        path: Annotated[str, Field(description="파일 경로")],
        line: Annotated[int, Field(description="댓글을 달 라인 번호")],
        side: Annotated[str, Field(description="LEFT (삭제) 또는 RIGHT (추가, 기본)", default="RIGHT")] = "RIGHT",
    ) -> str:
        """PR의 특정 코드 라인에 인라인 리뷰 댓글을 작성한다."""
        logger.info("gh_create_review_comment: %s #%d %s:%d", owner_repo, pull_number, path, line)
        raw = await _client(ctx).create_review_comment(
            owner_repo, pull_number, body=body, commit_id=commit_id, path=path, line=line, side=side
        )
        return json.dumps(
            {"id": raw.get("id"), "path": raw.get("path", ""), "line": raw.get("line"), "html_url": raw.get("html_url", "")},
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def gh_create_comment(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        issue_number: Annotated[int, Field(description="PR 또는 Issue 번호")],
        body: Annotated[str, Field(description="댓글 본문 (Markdown)")],
    ) -> str:
        """PR 또는 이슈에 일반 댓글을 작성한다."""
        logger.info("gh_create_comment: %s #%d", owner_repo, issue_number)
        raw = await _client(ctx).create_issue_comment(owner_repo, issue_number, body)
        return json.dumps(
            {"id": raw.get("id"), "body": raw.get("body", ""), "html_url": raw.get("html_url", "")},
            ensure_ascii=False,
            indent=2,
        )

    # ── 파일 커밋 ─────────────────────────────────────────────────────────

    @mcp.tool()
    async def gh_create_or_update_file(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        file_path: Annotated[str, Field(description="파일 경로 (예: src/app.py)")],
        message: Annotated[str, Field(description="커밋 메시지")],
        content: Annotated[str, Field(description="파일 내용 (텍스트)")],
        branch: Annotated[str, Field(description="커밋할 브랜치 (선택, 기본은 default branch)", default="")] = "",
    ) -> str:
        """파일을 생성하거나 수정하는 커밋을 만든다. author는 설정된 GITHUB_AUTHOR_EMAIL 기준으로 자동 적용된다."""
        logger.info("gh_create_or_update_file: %s %s", owner_repo, file_path)
        client = _client(ctx)
        sha = await client.get_file_sha(owner_repo, file_path, ref=branch or None)
        raw = await client.create_or_update_file(
            owner_repo,
            file_path,
            message=message,
            content_bytes=content.encode("utf-8"),
            branch=branch or None,
            sha=sha,
        )
        commit = raw.get("commit", {})
        author = commit.get("author", {})
        return json.dumps(
            {
                "sha": commit.get("sha", ""),
                "message": commit.get("message", ""),
                "author_name": author.get("name", ""),
                "author_email": author.get("email", ""),
                "html_url": commit.get("html_url", ""),
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def gh_get_comments(
        ctx: Context,
        owner_repo: Annotated[str, Field(description="저장소 경로 (예: owner/repo)")],
        issue_number: Annotated[int, Field(description="PR 또는 Issue 번호")],
        per_page: Annotated[int, Field(description="최대 결과 수", default=50)] = 50,
    ) -> str:
        """PR 또는 이슈의 일반 댓글 목록을 조회한다."""
        logger.info("gh_get_comments: %s #%d", owner_repo, issue_number)
        raw = await _client(ctx).get_issue_comments(owner_repo, issue_number, per_page=per_page)
        return json.dumps(
            [
                {
                    "id": c.get("id"),
                    "user": (c.get("user") or {}).get("login", ""),
                    "body": c.get("body", ""),
                    "created_at": c.get("created_at", ""),
                    "html_url": c.get("html_url", ""),
                }
                for c in raw
            ],
            ensure_ascii=False,
            indent=2,
        )