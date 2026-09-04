import json
import logging
import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class Analysis:
    summary: str
    purpose: str
    audience: str
    tags: list[str]


class DeepSeekClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _post(self, payload: dict) -> dict:
        if not self.settings.deepseek_api_key:
            raise RuntimeError("DeepSeek API key is not configured")
        last_error: Exception | None = None
        for attempt in range(self.settings.deepseek_max_retries + 1):
            try:
                response = httpx.post(
                    f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}"},
                    json=payload,
                    timeout=self.settings.deepseek_timeout_seconds,
                )
                response.raise_for_status()
                result = response.json()
                logger.info("deepseek completed", extra={"usage": result.get("usage", {})})
                return result
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                retryable = not isinstance(
                    exc, httpx.HTTPStatusError
                ) or exc.response.status_code in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }
                if not retryable or attempt >= self.settings.deepseek_max_retries:
                    raise
                time.sleep(0.5 * (2**attempt))
        raise RuntimeError("DeepSeek request failed") from last_error

    def agent_turn(self, messages: list[dict], tools: list[dict]) -> dict:
        payload = {
            "model": self.settings.deepseek_model,
            "thinking": {"type": "disabled"},
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "max_tokens": 1500,
        }
        return self._post(payload)["choices"][0]["message"]

    def analyze(self, title: str, text: str) -> Analysis:
        if not self.settings.deepseek_api_key:
            excerpt = text[:240].strip() or "该文件暂未提取到可读文本。"
            return Analysis(
                summary=excerpt,
                purpose=f"用于学习或复习《{title}》相关内容。",
                audience="相关课程的校内学习者",
                tags=[],
            )
        payload = {
            "model": self.settings.deepseek_model,
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是校园资料分类助手。只依据给定文本判断，不推测不存在的信息。"
                        "输出 JSON，字段为 summary、purpose、audience、tags；tags 是字符串数组。"
                    ),
                },
                {"role": "user", "content": f"标题：{title}\n正文：\n{text[:30000]}"},
            ],
            "max_tokens": 1200,
        }
        for _ in range(2):
            result = self._post(payload)
            content = result["choices"][0]["message"].get("content")
            if content:
                parsed = json.loads(content)
                return Analysis(
                    summary=str(parsed.get("summary", ""))[:2000],
                    purpose=str(parsed.get("purpose", ""))[:2000],
                    audience=str(parsed.get("audience", ""))[:1000],
                    tags=[str(tag)[:40] for tag in parsed.get("tags", [])[:10]],
                )
        raise RuntimeError("DeepSeek returned empty JSON twice")

    def answer_with_context(self, question: str, context: str) -> str:
        if not self.settings.deepseek_api_key:
            return f"我找到了以下校内资源：\n\n{context}" if context else "暂未找到匹配资源。"
        payload = {
            "model": self.settings.deepseek_model,
            "thinking": {"type": "disabled"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是校内资源搜索助手。只能推荐上下文中存在的资源，必须保留资源 ID，"
                        "不得编造链接或资料。无结果时明确说明。"
                    ),
                },
                {"role": "user", "content": f"问题：{question}\n\n检索结果：\n{context}"},
            ],
            "max_tokens": 1200,
        }
        result = self._post(payload)
        return result["choices"][0]["message"]["content"]


deepseek_client = DeepSeekClient()
