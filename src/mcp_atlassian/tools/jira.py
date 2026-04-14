"""JIRA MCP 도구 정의."""

from __future__ import annotations

import json
import logging
from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from ..jira.models import JiraComment, JiraIssue, JiraTransition
from ..utils.adf import text_to_adf

logger = logging.getLogger("mcp_atlassian.tools")


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