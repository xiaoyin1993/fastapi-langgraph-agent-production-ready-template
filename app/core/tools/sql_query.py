"""用于 LangGraph 的 SQL 查询工具。

本模块提供了一个可以与 LangGraph 配合使用的 SQL 查询工具，
用于查询 PostgreSQL 数据库。仅允许 SELECT 查询以确保安全性。
"""

import re

from langchain_core.tools import tool

from app.infrastructure.config import settings
from app.infrastructure.logging import logger


@tool
async def sql_query_tool(query: str) -> str:
    """执行 SQL 查询并返回结果。仅支持 SELECT 查询。

    Args:
        query: 要执行的 SQL 查询语句（仅限 SELECT）。

    Returns:
        查询结果的格式化文本。
    """
    # 安全检查：只允许 SELECT 语句
    cleaned = query.strip().upper()
    if not cleaned.startswith("SELECT"):
        return "错误：出于安全考虑，仅允许 SELECT 查询。"

    # 检查危险关键词
    dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "EXEC", "EXECUTE"]
    for keyword in dangerous_keywords:
        if re.search(rf"\b{keyword}\b", cleaned):
            return f"错误：查询中包含不允许的操作：{keyword}"

    try:
        import psycopg

        conninfo = (
            f"host={settings.POSTGRES_HOST} "
            f"port={settings.POSTGRES_PORT} "
            f"user={settings.POSTGRES_USER} "
            f"password={settings.POSTGRES_PASSWORD} "
            f"dbname={settings.POSTGRES_DB}"
        )

        async with await psycopg.AsyncConnection.connect(conninfo) as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                rows = await cur.fetchall()

                if not rows:
                    return "查询执行成功，但没有返回数据。"

                # 获取列名
                columns = [desc.name for desc in cur.description]
                result_lines = [" | ".join(columns)]
                result_lines.append(" | ".join(["---"] * len(columns)))

                for row in rows[:100]:  # 最多返回 100 行
                    result_lines.append(" | ".join(str(v) for v in row))

                total = len(rows)
                result = "\n".join(result_lines)

                if total > 100:
                    result += f"\n\n（共 {total} 行，仅显示前 100 行）"
                else:
                    result += f"\n\n（共 {total} 行）"

                logger.info("sql_query_executed", row_count=total, query=query[:100])
                return result

    except Exception as e:
        logger.exception("sql_query_failed", error=str(e), query=query[:100])
        return f"查询执行失败：{str(e)}"
