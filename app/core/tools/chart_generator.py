"""用于 LangGraph 的图表生成工具。

本模块提供了一个可以与 LangGraph 配合使用的图表生成工具，
使用 matplotlib 生成图表并返回图表描述。
"""

import base64
import io
import json

from langchain_core.tools import tool

from app.infrastructure.logging import logger


@tool
async def chart_generator_tool(
    chart_type: str,
    title: str,
    data: str,
    x_label: str = "",
    y_label: str = "",
) -> str:
    """根据数据生成图表。

    Args:
        chart_type: 图表类型，可选 "bar"（柱状图）、"line"（折线图）、"pie"（饼图）、"scatter"（散点图）。
        title: 图表标题。
        data: JSON 格式的数据，如 '{"labels": ["A","B","C"], "values": [10, 20, 30]}' 或
              '{"labels": ["A","B"], "datasets": [{"name": "系列1", "values": [10,20]}, {"name": "系列2", "values": [30,40]}]}'。
        x_label: X 轴标签（可选）。
        y_label: Y 轴标签（可选）。

    Returns:
        图表的 base64 编码图片和描述文本。
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # 设置中文字体支持
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        parsed_data = json.loads(data)
        labels = parsed_data.get("labels", [])
        values = parsed_data.get("values", [])
        datasets = parsed_data.get("datasets", [])

        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#161b22")

        # 设置颜色
        colors = ["#58a6ff", "#3fb950", "#d29922", "#f85149", "#a371f7", "#79c0ff", "#56d364"]
        ax.tick_params(colors="#8b949e")
        ax.xaxis.label.set_color("#8b949e")
        ax.yaxis.label.set_color("#8b949e")
        ax.title.set_color("#e6edf3")
        for spine in ax.spines.values():
            spine.set_color("#30363d")

        if chart_type == "bar":
            if datasets:
                import numpy as np
                x = np.arange(len(labels))
                width = 0.8 / len(datasets)
                for i, ds in enumerate(datasets):
                    ax.bar(x + i * width, ds["values"], width, label=ds["name"], color=colors[i % len(colors)])
                ax.set_xticks(x + width * (len(datasets) - 1) / 2)
                ax.set_xticklabels(labels)
                ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="#e6edf3")
            else:
                ax.bar(labels, values, color=colors[:len(labels)])
        elif chart_type == "line":
            if datasets:
                for i, ds in enumerate(datasets):
                    ax.plot(labels, ds["values"], marker="o", label=ds["name"], color=colors[i % len(colors)])
                ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="#e6edf3")
            else:
                ax.plot(labels, values, marker="o", color=colors[0])
        elif chart_type == "pie":
            ax.pie(values, labels=labels, autopct="%1.1f%%", colors=colors[:len(labels)],
                   textprops={"color": "#e6edf3"})
        elif chart_type == "scatter":
            ax.scatter(labels, values, color=colors[0], s=60)
        else:
            return f"不支持的图表类型：{chart_type}。请使用 bar、line、pie 或 scatter。"

        ax.set_title(title, fontsize=14, pad=15)
        if x_label:
            ax.set_xlabel(x_label)
        if y_label:
            ax.set_ylabel(y_label)

        plt.tight_layout()

        # 转为 base64
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")

        logger.info("chart_generated", chart_type=chart_type, title=title)
        return f"![{title}](data:image/png;base64,{img_base64})\n\n图表「{title}」已生成。"

    except json.JSONDecodeError:
        return "错误：数据格式不正确，请提供有效的 JSON 数据。"
    except Exception as e:
        logger.exception("chart_generation_failed", error=str(e))
        return f"图表生成失败：{str(e)}"
