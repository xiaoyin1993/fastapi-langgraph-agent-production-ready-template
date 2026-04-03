"""用于 LangGraph 的 DuckDuckGo 搜索工具。

本模块提供了一个可以与 LangGraph 配合使用的 DuckDuckGo 搜索工具，
用于执行网络搜索。最多返回 10 条搜索结果，并能优雅地处理错误。
"""

from langchain_community.tools import DuckDuckGoSearchResults

duckduckgo_search_tool = DuckDuckGoSearchResults(num_results=10, handle_tool_error=True)
