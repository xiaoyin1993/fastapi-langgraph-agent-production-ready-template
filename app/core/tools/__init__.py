"""LangGraph 工具集，用于增强大语言模型的能力。

这个包包含可以与 LangGraph 配合使用的自定义工具，用来扩展
大语言模型的能力。目前包括网络搜索和其他外部集成的工具。
"""

from langchain_core.tools.base import BaseTool

from .duckduckgo_search import duckduckgo_search_tool

tools: list[BaseTool] = [duckduckgo_search_tool]
