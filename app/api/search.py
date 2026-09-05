import json

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.db import get_db
from app.models import Resource, ResourceStatus, User
from app.schemas import (
    AgentRequest,
    AgentResponse,
    ResourceDetailsToolArguments,
    ResourceView,
    SearchResult,
    SearchToolArguments,
)
from app.services.deepseek import deepseek_client
from app.services.rate_limit import enforce_rate_limit
from app.services.search import search_resources

router = APIRouter(tags=["search"])

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_resources",
            "description": "在已发布的校内资料中搜索，支持课程、分类和文件类型过滤。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "course": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"]},
                    "file_type": {"type": ["string", "null"]},
                },
                "required": ["query", "course", "category", "file_type"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_resource_details",
            "description": "根据资源 ID 查看一个已发布资源的详细信息。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {"resource_id": {"type": "string"}},
                "required": ["resource_id"],
                "additionalProperties": False,
            },
        },
    },
]


@router.get("/search", response_model=list[SearchResult])
def search(
    q: str = Query(min_length=1, max_length=300),
    course: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(current_user),
) -> list[SearchResult]:
    return search_resources(db, q, course, category, viewer_id=_user.id)


@router.post("/agent/chat", response_model=AgentResponse)
def agent_chat(
    payload: AgentRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(current_user),
) -> AgentResponse:
    enforce_rate_limit(f"agent:{_user.id}", 30, 3600)
    if not get_settings().deepseek_api_key:
        results = search_resources(db, payload.message, limit=8, viewer_id=_user.id)
        context = _results_context(results)
        return AgentResponse(
            answer=deepseek_client.answer_with_context(payload.message, context),
            resources=results,
        )

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "你是校内资源搜索助手。先调用工具检索，只能推荐工具返回的资源；"
                "回答中保留资源标题和 ID。禁止编造资源或外部链接。"
            ),
        },
        {"role": "user", "content": payload.message},
    ]
    collected: dict[str, SearchResult] = {}
    for _ in range(4):
        message = deepseek_client.agent_turn(messages, AGENT_TOOLS)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            answer = message.get("content") or "暂未找到匹配资源。"
            return AgentResponse(answer=answer, resources=list(collected.values()))
        messages.append(
            {"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls}
        )
        for call in tool_calls:
            name = call.get("function", {}).get("name")
            try:
                raw_arguments = json.loads(call.get("function", {}).get("arguments", "{}"))
                if name == "search_resources":
                    arguments = SearchToolArguments.model_validate(raw_arguments)
                    results = search_resources(
                        db,
                        arguments.query,
                        arguments.course,
                        arguments.category,
                        arguments.file_type,
                        limit=8,
                        viewer_id=_user.id,
                    )
                    for item in results:
                        collected[item.resource.id] = item
                    output = [item.model_dump(mode="json") for item in results]
                elif name == "get_resource_details":
                    arguments = ResourceDetailsToolArguments.model_validate(raw_arguments)
                    resource = db.scalar(
                        select(Resource).where(
                            Resource.id == arguments.resource_id,
                            Resource.status == ResourceStatus.PUBLISHED,
                        )
                    )
                    output = (
                        ResourceView.model_validate(resource).model_dump(mode="json")
                        if resource
                        else None
                    )
                else:
                    output = {"error": "不允许调用该工具"}
            except (ValidationError, json.JSONDecodeError) as exc:
                output = {"error": "工具参数无效", "details": str(exc)}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": json.dumps(output, ensure_ascii=False),
                }
            )
    return AgentResponse(
        answer="检索步骤过多，请缩小查询范围后重试。",
        resources=list(collected.values()),
    )


def _results_context(results: list[SearchResult]) -> str:
    context = "\n\n".join(
        f"资源 ID: {item.resource.id}\n标题: {item.resource.title}\n"
        f"课程: {item.resource.course or '未标注'}\n用途: {item.resource.ai_purpose or item.resource.description}\n"
        f"使用经验: {item.resource.experience}\n匹配内容: {item.matched_excerpt or ''}"
        for item in results
    )
    return context
