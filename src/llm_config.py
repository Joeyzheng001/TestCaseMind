"""
LLM 配置读取

支持 Anthropic 原生接口，也支持提供 Anthropic 兼容端点的模型服务
（例如在 .env 中配置 ANTHROPIC_BASE_URL 指向 DeepSeek 兼容接口）。
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    provider: str
    api_key: Optional[str]
    auth_token: Optional[str]
    base_url: Optional[str]
    model: str
    auth_mode: str
    max_tokens: int = 8000


def load_llm_config(api_key: Optional[str] = None) -> LLMConfig:
    provider = os.getenv("LLM_PROVIDER") or _infer_provider()
    resolved_api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    auth_mode = os.getenv("ANTHROPIC_AUTH_MODE", "api_key").strip().lower()
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    model = (
        os.getenv("ANTHROPIC_MODEL")
        or os.getenv("MODEL_ID")
        or "deepseek-v4-pro"
    )
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "8000"))

    return LLMConfig(
        provider=provider,
        api_key=resolved_api_key,
        auth_token=auth_token,
        base_url=base_url,
        model=model,
        auth_mode=auth_mode,
        max_tokens=max_tokens,
    )


def _infer_provider() -> str:
    base_url = (os.getenv("ANTHROPIC_BASE_URL") or "").lower()
    model = (os.getenv("MODEL_ID") or os.getenv("ANTHROPIC_MODEL") or "").lower()

    markers = {
        "deepseek": ("deepseek",),
        "minimax": ("minimax",),
        "moonshot": ("moonshot",),
        "zhipu": ("bigmodel",),
        "qwen": ("dashscope", "qwen"),
        "bytedance": ("volces", "doubao"),
        "openai": ("openai",),
    }
    for provider, keywords in markers.items():
        for kw in keywords:
            if kw in base_url or kw in model:
                return provider
    return "deepseek"
