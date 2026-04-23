"""JIRA MCP 도구 정의."""

from __future__ import annotations

import json
import logging
from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from ..jira.models import JiraComment, JiraIssue, JiraTransition
from ..utils.adf import text_to_adf

logger = logging.getLogger("mcp_gateway.tools.jira")


def register_tools(mcp: FastMCP) -> None:
    """MCP 서버에 JIRA 도구들을 등록한다."""

    @mcp.tool()
    async def get_issue(
        ctx: Context,
        issue_key: Annotated[str, Field(description="JIRA 이슈 키 (예: APTI-5266)")],
    ) -> str:
        """JIRA 이슈 상세 정보를 조회한다."""
        logger.info("get_issue 호출: %s", issue_key)
        client = ctx.request_context.lifespan_context["jira_client"]
        raw = await client.get_issue(issue_key)
        issue = JiraIssue.from_raw(raw)
        logger.info("get_issue 완료: %s", issue_key)
        return json.dumps(issue, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def get_comments(
        ctx: Context,
        issue_key: Annotated[str, Field(description="JIRA 이슈 키 (예: APTI-5266)")],
    ) -> str:
        """JIRA 이슈의 댓글 목록을 조회한다."""
        logger.info("get_comments 호출: %s", issue_key)
        client = ctx.request_context.lifespan_context["jira_client"]
        raw = await client.get_comments(issue_key)
        comments = [JiraComment.from_raw(c) for c in raw.get("comments", [])]
        logger.info("get_comments 완료: %s → %d건", issue_key, len(comments))
        return json.dumps(comments, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def add_comment(
        ctx: Context,
        issue_key: Annotated[str, Field(description="JIRA 이슈 키 (예: APTI-5266)")],
        body: Annotated[str, Field(description="댓글 내용 (텍스트)")],
    ) -> str:
        """JIRA 이슈에 댓글을 추가한다."""
        logger.info("add_comment 호출: %s", issue_key)
        client = ctx.request_context.lifespan_context["jira_client"]
        adf_body = {"body": text_to_adf(body)}
        raw = await client.add_comment(issue_key, adf_body)
        comment = JiraComment.from_raw(raw)
        logger.info("add_comment 완료: %s", issue_key)
        return json.dumps(comment, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def update_comment(
        ctx: Context,
        issue_key: Annotated[str, Field(description="JIRA 이슈 키 (예: APTI-5266)")],
        comment_id: Annotated[str, Field(description="수정할 댓글 ID")],
        body: Annotated[str, Field(description="변경할 댓글 내용 (텍스트)")],
    ) -> str:
        """JIRA 이슈 댓글을 수정한다."""
        logger.info("update_comment 호출: %s / %s", issue_key, comment_id)
        client = ctx.request_context.lifespan_context["jira_client"]
        adf_body = {"body": text_to_adf(body)}
        raw = await client.update_comment(issue_key, comment_id, adf_body)
        comment = JiraComment.from_raw(raw)
        logger.info("update_comment 완료: %s / %s", issue_key, comment_id)
        return json.dumps(comment, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def delete_comment(
        ctx: Context,
        issue_key: Annotated[str, Field(description="JIRA 이슈 키 (예: APTI-5266)")],
        comment_id: Annotated[str, Field(description="삭제할 댓글 ID")],
    ) -> str:
        """JIRA 이슈 댓글을 삭제한다."""
        logger.info("delete_comment 호출: %s / %s", issue_key, comment_id)
        client = ctx.request_context.lifespan_context["jira_client"]
        await client.delete_comment(issue_key, comment_id)
        logger.info("delete_comment 완료: %s / %s", issue_key, comment_id)
        return json.dumps(
            {"success": True, "issue_key": issue_key, "comment_id": comment_id},
            ensure_ascii=False,
        )

    @mcp.tool()
    async def create_issue(
        ctx: Context,
        project_key: Annotated[str, Field(description="프로젝트 키 (예: APTI)")],
        summary: Annotated[str, Field(description="이슈 제목")],
        issue_type: Annotated[str, Field(description="이슈 타입 (예: Task, Bug, Story)", default="Task")] = "Task",
        description: Annotated[str, Field(description="이슈 설명 (텍스트)", default="")] = "",
        assignee_account_id: Annotated[
            str,
            Field(description="담당자 Atlassian accountId (선택)", default=""),
        ] = "",
        priority: Annotated[str, Field(description="우선순위 이름 (선택, 예: Medium)", default="")] = "",
    ) -> str:
        """JIRA 이슈를 생성한다."""
        logger.info("create_issue 호출: project=%s, summary=%s", project_key, summary)
        client = ctx.request_context.lifespan_context["jira_client"]
        fields: dict = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description:
            fields["description"] = text_to_adf(description)
        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}
        if priority:
            fields["priority"] = {"name": priority}
        raw = await client.create_issue(fields)
        logger.info("create_issue 완료: %s", raw.get("key", ""))
        return json.dumps(
            {
                "key": raw.get("key", ""),
                "id": raw.get("id", ""),
                "self": raw.get("self", ""),
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def update_issue(
        ctx: Context,
        issue_key: Annotated[str, Field(description="JIRA 이슈 키 (예: APTI-5266)")],
        summary: Annotated[str, Field(description="변경할 제목 (선택)", default="")] = "",
        description: Annotated[str, Field(description="변경할 설명 텍스트 (선택)", default="")] = "",
        assignee_account_id: Annotated[
            str,
            Field(description="변경할 담당자 accountId (선택, 빈 문자열은 무시)", default=""),
        ] = "",
        priority: Annotated[str, Field(description="변경할 우선순위 이름 (선택)", default="")] = "",
    ) -> str:
        """JIRA 이슈의 필드를 수정한다. 지정하지 않은 필드는 변경되지 않는다."""
        logger.info("update_issue 호출: %s", issue_key)
        client = ctx.request_context.lifespan_context["jira_client"]
        fields: dict = {}
        if summary:
            fields["summary"] = summary
        if description:
            fields["description"] = text_to_adf(description)
        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}
        if priority:
            fields["priority"] = {"name": priority}
        if not fields:
            return json.dumps(
                {"success": False, "error": "변경할 필드가 없습니다."},
                ensure_ascii=False,
            )
        await client.update_issue(issue_key, fields)
        logger.info("update_issue 완료: %s (%s)", issue_key, ", ".join(fields.keys()))
        return json.dumps(
            {"success": True, "issue_key": issue_key, "updated_fields": list(fields.keys())},
            ensure_ascii=False,
        )

    @mcp.tool()
    async def search_issues(
        ctx: Context,
        jql: Annotated[str, Field(description="JQL 쿼리 (예: project=APTI AND status='진행 중')")],
        max_results: Annotated[int, Field(description="최대 결과 수", default=20)] = 20,
    ) -> str:
        """JQL 쿼리로 JIRA 이슈를 검색한다."""
        logger.info("search_issues 호출: jql=%s, max_results=%d", jql, max_results)
        client = ctx.request_context.lifespan_context["jira_client"]
        raw = await client.search_issues(jql, max_results)
        issues = [JiraIssue.from_raw(i) for i in raw.get("issues", [])]
        result = {
            "total": raw.get("total", 0),
            "issues": issues,
        }
        logger.info("search_issues 완료: %d건 조회", len(issues))
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def get_transitions(
        ctx: Context,
        issue_key: Annotated[str, Field(description="JIRA 이슈 키 (예: APTI-5266)")],
    ) -> str:
        """JIRA 이슈의 가능한 상태 변경 목록을 조회한다."""
        logger.info("get_transitions 호출: %s", issue_key)
        client = ctx.request_context.lifespan_context["jira_client"]
        raw = await client.get_transitions(issue_key)
        transitions = [JiraTransition.from_raw(t) for t in raw.get("transitions", [])]
        logger.info("get_transitions 완료: %s → %d건", issue_key, len(transitions))
        return json.dumps(transitions, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def transition_issue(
        ctx: Context,
        issue_key: Annotated[str, Field(description="JIRA 이슈 키 (예: APTI-5266)")],
        transition_id: Annotated[str, Field(description="트랜지션 ID (get_transitions로 조회)")],
    ) -> str:
        """JIRA 이슈의 상태를 변경한다."""
        logger.info("transition_issue 호출: %s → transition_id=%s", issue_key, transition_id)
        client = ctx.request_context.lifespan_context["jira_client"]
        await client.transition_issue(issue_key, transition_id)
        logger.info("transition_issue 완료: %s", issue_key)
        return json.dumps(
            {"success": True, "issue_key": issue_key, "transition_id": transition_id},
            ensure_ascii=False,
        )