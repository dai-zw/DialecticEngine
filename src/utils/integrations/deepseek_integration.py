"""DeepSeek LLM 集成模块。

使用 LangChain 官方 DeepSeek SDK 进行封装。
需要安装: pip install langchain-deepseek
"""

import os
from dotenv import load_dotenv

load_dotenv()

from typing import Any, Dict, List, Optional, Iterator, Union
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_deepseek import ChatDeepSeek


def create_chat_model(
    model_name: str = "deepseek-chat",
    temperature: float = 0.7,
    api_key: str = None,
    request_timeout: int = 120,
) -> ChatDeepSeek:
    """快捷创建 DeepSeek 聊天模型的工厂函数。

    Args:
        model_name: 模型名称，默认 deepseek-chat
        temperature: 温度参数
        api_key: API密钥，默认从环境变量读取
        request_timeout: 请求超时时间（秒）

    Returns:
        ChatDeepSeek 实例

    Example:
        llm = create_chat_model(temperature=0.9)
        response = llm.invoke("你好")
        for chunk in llm.stream("你好"):
            print(chunk.content, end="", flush=True)
    """
    return ChatDeepSeek(
        model=model_name,
        temperature=temperature,
        api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
        request_timeout=request_timeout,
    )


# 向后兼容的别名
DeepSeekChat = ChatDeepSeek


