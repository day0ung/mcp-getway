"""GitLab MCP 도구 정의."""

from __future__ import annotations

import base64
import json
import logging
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from ..gitlab.models import (
    GitLabBranch,
    GitLabCommit,
    GitLabDiff,
    GitLabMergeRequest,
    GitLabProject,
)

logger = logging.getLogger("mcp_gateway.tools.gitlab")


def _client(ctx: Context):
    return ctx.request_context.lifespan_context["gitlab_client"]


def register_tools(mcp: FastMCP) -> None:
    """MCP 서버에 GitLab 도구들을 등록한다."""

    # ── Projects / Repository ────────────────────────────────────────────

    @mcp.tool()
    async def list_projects(
        ctx: Context,
        search: Annotated[str, Field(description="프로젝트 이름 검색어 (선택)", default="")] = "",
        membership: Annotated[bool, Field(description="내가 속한 프로젝트만", default=True)] = True,
        per_page: Annotated[int, Field(description="최대 결과 수", default=20)] = 20,
    ) -> str:
        """GitLab 프로젝트 목록을 조회한다."""
        logger.info("list_projects: search=%s membership=%s", search, membership)
        raw = await _client(ctx).list_projects(search=search or None, membership=membership, per_page=per_page)
        return json.dumps(
            [GitLabProject.summary(p) for p in raw],
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def get_project(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID(숫자) 또는 경로 (예: group/subgroup/project)")],
    ) -> str:
        """GitLab 프로젝트 상세 정보를 조회한다."""
        logger.info("get_project: %s", project_id)
        raw = await _client(ctx).get_project(project_id)
        return json.dumps(GitLabProject.summary(raw), ensure_ascii=False, indent=2)

    @mcp.tool()
    async def get_file_contents(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        file_path: Annotated[str, Field(description="파일 경로 (예: src/app.py)")],
        ref: Annotated[str, Field(description="브랜치/태그/SHA (기본: HEAD)", default="HEAD")] = "HEAD",
    ) -> str:
        """GitLab 프로젝트에서 파일 내용을 조회한다. 텍스트 파일이면 decoded_content 필드에 복호화된 내용을 담는다."""
        logger.info("get_file_contents: %s@%s %s", project_id, ref, file_path)
        raw = await _client(ctx).get_file_contents(project_id, file_path, ref=ref)
        out: dict[str, Any] = {
            "file_path": raw.get("file_path", ""),
            "ref": raw.get("ref", ""),
            "size": raw.get("size", 0),
            "encoding": raw.get("encoding", ""),
            "content_sha256": raw.get("content_sha256", ""),
            "blob_id": raw.get("blob_id", ""),
            "last_commit_id": raw.get("last_commit_id", ""),
        }
        if raw.get("encoding") == "base64" and raw.get("content"):
            try:
                out["decoded_content"] = base64.b64decode(raw["content"]).decode("utf-8")
            except UnicodeDecodeError:
                out["decoded_content"] = None
                out["note"] = "바이너리 파일로 판단되어 decoded_content 를 제공하지 않음"
        else:
            out["content"] = raw.get("content", "")
        return json.dumps(out, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def get_repository_tree(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        path: Annotated[str, Field(description="디렉토리 경로 (선택, 기본은 레포 루트)", default="")] = "",
        ref: Annotated[str, Field(description="브랜치/태그/SHA (선택)", default="")] = "",
        recursive: Annotated[bool, Field(description="하위 디렉토리까지 재귀적으로 조회", default=False)] = False,
        per_page: Annotated[int, Field(description="최대 결과 수", default=100)] = 100,
    ) -> str:
        """GitLab 프로젝트의 디렉토리 트리를 조회한다."""
        logger.info("get_repository_tree: %s path=%s ref=%s recursive=%s", project_id, path, ref, recursive)
        raw = await _client(ctx).get_repository_tree(
            project_id, path=path, ref=ref or None, recursive=recursive, per_page=per_page
        )
        return json.dumps(raw, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def list_commits(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        ref_name: Annotated[str, Field(description="브랜치/태그 (선택)", default="")] = "",
        since: Annotated[str, Field(description="ISO 8601 날짜 이후 (선택, 예: 2026-01-01T00:00:00Z)", default="")] = "",
        until: Annotated[str, Field(description="ISO 8601 날짜 이전 (선택)", default="")] = "",
        per_page: Annotated[int, Field(description="최대 결과 수", default=20)] = 20,
    ) -> str:
        """GitLab 프로젝트의 커밋 이력을 조회한다."""
        logger.info("list_commits: %s ref=%s", project_id, ref_name)
        raw = await _client(ctx).list_commits(
            project_id, ref_name=ref_name or None, since=since or None, until=until or None, per_page=per_page
        )
        return json.dumps([GitLabCommit.summary(c) for c in raw], ensure_ascii=False, indent=2)

    # ── Branches ─────────────────────────────────────────────────────────

    @mcp.tool()
    async def list_branches(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        search: Annotated[str, Field(description="브랜치 이름 검색어 (선택)", default="")] = "",
        per_page: Annotated[int, Field(description="최대 결과 수", default=50)] = 50,
    ) -> str:
        """GitLab 프로젝트의 브랜치 목록을 조회한다."""
        logger.info("list_branches: %s search=%s", project_id, search)
        raw = await _client(ctx).list_branches(project_id, search=search or None, per_page=per_page)
        return json.dumps([GitLabBranch.summary(b) for b in raw], ensure_ascii=False, indent=2)

    @mcp.tool()
    async def create_branch(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        branch: Annotated[str, Field(description="새로 만들 브랜치 이름")],
        ref: Annotated[str, Field(description="분기 기준이 될 브랜치/태그/SHA")],
    ) -> str:
        """GitLab 프로젝트에 새 브랜치를 생성한다."""
        logger.info("create_branch: %s %s ← %s", project_id, branch, ref)
        raw = await _client(ctx).create_branch(project_id, branch=branch, ref=ref)
        return json.dumps(GitLabBranch.summary(raw), ensure_ascii=False, indent=2)

    @mcp.tool()
    async def get_branch_diffs(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        from_ref: Annotated[str, Field(description="비교 시작 브랜치/SHA (base)")],
        to_ref: Annotated[str, Field(description="비교 대상 브랜치/SHA (head)")],
        straight: Annotated[bool, Field(description="직선 비교 (기본 false = merge-base 기준)", default=False)] = False,
    ) -> str:
        """두 브랜치/커밋 사이의 변경사항(diff)을 조회한다."""
        logger.info("get_branch_diffs: %s %s…%s straight=%s", project_id, from_ref, to_ref, straight)
        raw = await _client(ctx).get_branch_diffs(project_id, from_ref=from_ref, to_ref=to_ref, straight=straight)
        return json.dumps(raw, ensure_ascii=False, indent=2)

    # ── Merge Requests ──────────────────────────────────────────────────

    @mcp.tool()
    async def list_merge_requests(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        state: Annotated[str, Field(description="opened / closed / merged / all", default="opened")] = "opened",
        source_branch: Annotated[str, Field(description="소스 브랜치 필터 (선택)", default="")] = "",
        target_branch: Annotated[str, Field(description="타겟 브랜치 필터 (선택)", default="")] = "",
        search: Annotated[str, Field(description="제목/설명 검색어 (선택)", default="")] = "",
        per_page: Annotated[int, Field(description="최대 결과 수", default=20)] = 20,
    ) -> str:
        """프로젝트의 MR 목록을 조회한다."""
        logger.info("list_merge_requests: %s state=%s", project_id, state)
        raw = await _client(ctx).list_merge_requests(
            project_id,
            state=state,
            source_branch=source_branch or None,
            target_branch=target_branch or None,
            search=search or None,
            per_page=per_page,
        )
        return json.dumps([GitLabMergeRequest.summary(m) for m in raw], ensure_ascii=False, indent=2)

    @mcp.tool()
    async def get_merge_request(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        merge_request_iid: Annotated[int, Field(description="MR iid (프로젝트 내부 번호)")],
    ) -> str:
        """MR 상세 정보를 조회한다."""
        logger.info("get_merge_request: %s !%d", project_id, merge_request_iid)
        raw = await _client(ctx).get_merge_request(project_id, merge_request_iid)
        return json.dumps(GitLabMergeRequest.summary(raw), ensure_ascii=False, indent=2)

    @mcp.tool()
    async def create_merge_request(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        source_branch: Annotated[str, Field(description="소스 브랜치")],
        target_branch: Annotated[str, Field(description="타겟 브랜치")],
        title: Annotated[str, Field(description="MR 제목")],
        description: Annotated[str, Field(description="MR 설명 (Markdown)", default="")] = "",
        remove_source_branch: Annotated[bool, Field(description="머지 후 소스 브랜치 삭제", default=False)] = False,
        draft: Annotated[bool, Field(description="Draft(WIP)로 생성", default=False)] = False,
    ) -> str:
        """새 Merge Request를 생성한다."""
        logger.info(
            "create_merge_request: %s %s → %s title=%s",
            project_id,
            source_branch,
            target_branch,
            title,
        )
        raw = await _client(ctx).create_merge_request(
            project_id,
            source_branch=source_branch,
            target_branch=target_branch,
            title=title,
            description=description,
            remove_source_branch=remove_source_branch,
            draft=draft,
        )
        return json.dumps(GitLabMergeRequest.summary(raw), ensure_ascii=False, indent=2)

    @mcp.tool()
    async def get_merge_request_diffs(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        merge_request_iid: Annotated[int, Field(description="MR iid")],
        page: Annotated[int, Field(description="페이지 번호", default=1)] = 1,
        per_page: Annotated[int, Field(description="페이지 크기", default=20)] = 20,
        unidiff: Annotated[bool, Field(description="unified diff 포맷으로 요청", default=False)] = False,
    ) -> str:
        """MR 의 전체 diff 목록을 조회한다 (파일별 diff 본문 포함)."""
        logger.info("get_merge_request_diffs: %s !%d page=%d", project_id, merge_request_iid, page)
        raw = await _client(ctx).get_merge_request_diffs(
            project_id, merge_request_iid, page=page, per_page=per_page, unidiff=unidiff
        )
        return json.dumps(raw, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def list_merge_request_changed_files(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        merge_request_iid: Annotated[int, Field(description="MR iid")],
        excluded_file_patterns: Annotated[
            str,
            Field(
                description="제외할 경로 정규식 패턴 (선택, 쉼표로 여러 개. 예: ^dist/,\\.lock$)",
                default="",
            ),
        ] = "",
    ) -> str:
        """[리뷰 1단계] MR 의 변경된 파일 경로 목록만 반환한다 (diff 본문 없음).

        diff 본문이 필요하면 get_merge_request_file_diff 로 파일 단위로 가져와라.
        """
        import re

        logger.info("list_merge_request_changed_files: %s !%d", project_id, merge_request_iid)
        raw = await _client(ctx).get_merge_request_diffs(
            project_id, merge_request_iid, page=1, per_page=100
        )
        patterns = [p.strip() for p in excluded_file_patterns.split(",") if p.strip()]
        compiled = [re.compile(p) for p in patterns]
        results = []
        for d in raw:
            path = GitLabDiff.file_path(d)
            if any(c.search(path) for c in compiled):
                continue
            results.append(GitLabDiff.changed_file_summary(d))
        return json.dumps({"count": len(results), "files": results}, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def get_merge_request_file_diff(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        merge_request_iid: Annotated[int, Field(description="MR iid")],
        file_paths: Annotated[
            str,
            Field(description="diff를 받을 파일 경로 (쉼표로 여러 개, 권장 3~5개). new_path 또는 old_path 기준"),
        ],
        unidiff: Annotated[bool, Field(description="unified diff 포맷", default=False)] = False,
    ) -> str:
        """[리뷰 2단계] 지정한 파일들의 diff 본문을 반환한다 (배치 조회)."""
        logger.info(
            "get_merge_request_file_diff: %s !%d files=%s",
            project_id,
            merge_request_iid,
            file_paths,
        )
        wanted = {p.strip() for p in file_paths.split(",") if p.strip()}
        # per_page 큰 값으로 한 번에 받고 파이썬 쪽에서 필터링
        raw = await _client(ctx).get_merge_request_diffs(
            project_id, merge_request_iid, page=1, per_page=200, unidiff=unidiff
        )
        matched = [
            d for d in raw if d.get("new_path") in wanted or d.get("old_path") in wanted
        ]
        return json.dumps({"count": len(matched), "diffs": matched}, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def approve_merge_request(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        merge_request_iid: Annotated[int, Field(description="MR iid")],
    ) -> str:
        """MR을 승인(Approve)한다."""
        logger.info("approve_merge_request: %s !%d", project_id, merge_request_iid)
        raw = await _client(ctx).approve_merge_request(project_id, merge_request_iid)
        return json.dumps(raw, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def merge_merge_request(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        merge_request_iid: Annotated[int, Field(description="MR iid")],
        merge_commit_message: Annotated[str, Field(description="머지 커밋 메시지 (선택)", default="")] = "",
        squash: Annotated[bool, Field(description="squash 머지", default=False)] = False,
        should_remove_source_branch: Annotated[bool, Field(description="머지 후 소스 브랜치 삭제", default=False)] = False,
        merge_when_pipeline_succeeds: Annotated[bool, Field(description="파이프라인 성공 시 자동 머지", default=False)] = False,
    ) -> str:
        """MR을 머지한다."""
        logger.info("merge_merge_request: %s !%d squash=%s", project_id, merge_request_iid, squash)
        raw = await _client(ctx).merge_merge_request(
            project_id,
            merge_request_iid,
            merge_commit_message=merge_commit_message or None,
            squash=squash,
            should_remove_source_branch=should_remove_source_branch,
            merge_when_pipeline_succeeds=merge_when_pipeline_succeeds,
        )
        return json.dumps(GitLabMergeRequest.summary(raw), ensure_ascii=False, indent=2)

    # ── MR 리뷰 ──────────────────────────────────────────────────────────

    @mcp.tool()
    async def create_note(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        merge_request_iid: Annotated[int, Field(description="MR iid")],
        body: Annotated[str, Field(description="댓글 본문 (Markdown)")],
    ) -> str:
        """MR에 단일 노트(댓글)를 작성한다 (스레드가 아닌 일반 코멘트)."""
        logger.info("create_note: %s !%d", project_id, merge_request_iid)
        raw = await _client(ctx).create_note(project_id, merge_request_iid, body)
        return json.dumps(
            {"id": raw.get("id"), "body": raw.get("body", ""), "author": (raw.get("author") or {}).get("username", "")},
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def mr_discussions(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        merge_request_iid: Annotated[int, Field(description="MR iid")],
        per_page: Annotated[int, Field(description="최대 결과 수", default=50)] = 50,
    ) -> str:
        """MR의 discussion(스레드) 목록을 조회한다."""
        logger.info("mr_discussions: %s !%d", project_id, merge_request_iid)
        raw = await _client(ctx).mr_discussions(project_id, merge_request_iid, per_page=per_page)
        return json.dumps(raw, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def create_merge_request_thread(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        merge_request_iid: Annotated[int, Field(description="MR iid")],
        body: Annotated[str, Field(description="첫 댓글 본문 (Markdown)")],
        position_json: Annotated[
            str,
            Field(
                description=(
                    "코드 라인에 달 경우 position 오브젝트의 JSON 문자열 (선택).\n"
                    "필수 키: base_sha, start_sha, head_sha, position_type='text',"
                    " new_path, new_line (삭제 라인이면 old_path, old_line)"
                ),
                default="",
            ),
        ] = "",
    ) -> str:
        """MR 에 새 스레드(discussion)를 시작한다. position_json을 주면 코드 라인에 인라인 코멘트."""
        logger.info("create_merge_request_thread: %s !%d", project_id, merge_request_iid)
        position = json.loads(position_json) if position_json else None
        raw = await _client(ctx).create_merge_request_thread(
            project_id, merge_request_iid, body=body, position=position
        )
        return json.dumps(raw, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def create_draft_note(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        merge_request_iid: Annotated[int, Field(description="MR iid")],
        body: Annotated[str, Field(description="초안 댓글 본문 (Markdown)")],
        position_json: Annotated[
            str,
            Field(description="코드 라인 position JSON (선택, create_merge_request_thread와 동일)", default=""),
        ] = "",
        in_reply_to_discussion_id: Annotated[
            str,
            Field(description="답글로 달고 싶은 기존 discussion id (선택)", default=""),
        ] = "",
    ) -> str:
        """MR 리뷰 초안(draft note)을 생성한다. bulk_publish_draft_notes 로 일괄 게시할 수 있다."""
        logger.info("create_draft_note: %s !%d", project_id, merge_request_iid)
        position = json.loads(position_json) if position_json else None
        raw = await _client(ctx).create_draft_note(
            project_id,
            merge_request_iid,
            body=body,
            position=position,
            in_reply_to_discussion_id=in_reply_to_discussion_id or None,
        )
        return json.dumps(raw, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def bulk_publish_draft_notes(
        ctx: Context,
        project_id: Annotated[str, Field(description="프로젝트 ID 또는 경로")],
        merge_request_iid: Annotated[int, Field(description="MR iid")],
    ) -> str:
        """현재 MR에 쌓인 내 draft note 들을 일괄 게시한다."""
        logger.info("bulk_publish_draft_notes: %s !%d", project_id, merge_request_iid)
        raw = await _client(ctx).bulk_publish_draft_notes(project_id, merge_request_iid)
        return json.dumps(
            {"success": True, "project_id": project_id, "merge_request_iid": merge_request_iid, "response": raw},
            ensure_ascii=False,
            indent=2,
        )