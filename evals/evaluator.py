"""评估模块的评估器。"""

import asyncio
import os
import sys
import time
from datetime import (
    datetime,
    timedelta,
)
from time import sleep

import openai
from langfuse import Langfuse
from langfuse.api.resources.commons.types.trace_with_details import TraceWithDetails
from tqdm import tqdm

# 修复 app 模块的导入路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.infrastructure.config import settings
from app.infrastructure.logging import logger
from evals.helpers import (
    calculate_avg_scores,
    generate_report,
    get_input_output,
    initialize_metrics_summary,
    initialize_report,
    process_trace_results,
    update_failure_metrics,
    update_success_metrics,
)
from evals.metrics import metrics
from evals.schemas import ScoreSchema


class Evaluator:
    """使用预定义指标来评估模型输出。

    这个类负责从 Langfuse 获取 trace，用各项指标对它们进行评估，
    然后把评分结果上传回 Langfuse。

    Attributes:
        client: 用于 API 调用的 OpenAI 客户端。
        langfuse: 用于 trace 管理的 Langfuse 客户端。
    """

    def __init__(self):
        """初始化评估器，创建 OpenAI 和 Langfuse 客户端。"""
        self.client = openai.AsyncOpenAI(api_key=settings.EVALUATION_API_KEY, base_url=settings.EVALUATION_BASE_URL)
        self.langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            timeout=60,  # 单位：秒
        )
        # 初始化报告数据结构
        self.report = initialize_report(settings.EVALUATION_LLM)
        initialize_metrics_summary(self.report, metrics)

    async def run(self, generate_report_file=True):
        """主执行函数，获取 trace 并进行评估。

        从 Langfuse 获取 trace，对每条 trace 用所有指标进行评估，
        然后将评分上传回 Langfuse。

        Args:
            generate_report_file: 是否在评估后生成 JSON 报告，默认为 True。
        """
        start_time = time.time()
        traces = self.__fetch_traces()
        self.report["total_traces"] = len(traces)

        trace_results = {}

        for trace in tqdm(traces, desc="Evaluating traces"):
            trace_id = trace.id
            trace_results[trace_id] = {
                "success": False,
                "metrics_evaluated": 0,
                "metrics_succeeded": 0,
                "metrics_results": {},
            }

            for metric in tqdm(metrics, desc=f"Applying metrics to trace {trace_id[:8]}...", leave=False):
                metric_name = metric["name"]
                input, output = get_input_output(trace)
                score = await self._run_metric_evaluation(metric, input, output)

                if score:
                    self._push_to_langfuse(trace, score, metric)
                    update_success_metrics(self.report, trace_id, metric_name, score, trace_results)
                else:
                    update_failure_metrics(self.report, trace_id, metric_name, trace_results)

                trace_results[trace_id]["metrics_evaluated"] += 1

            process_trace_results(self.report, trace_id, trace_results, len(metrics))
            sleep(settings.EVALUATION_SLEEP_TIME)

        self.report["duration_seconds"] = round(time.time() - start_time, 2)
        calculate_avg_scores(self.report)

        if generate_report_file:
            generate_report(self.report)

        logger.info(
            "Evaluation completed",
            total_traces=self.report["total_traces"],
            successful_traces=self.report["successful_traces"],
            failed_traces=self.report["failed_traces"],
            duration_seconds=self.report["duration_seconds"],
        )

    def _push_to_langfuse(self, trace: TraceWithDetails, score: ScoreSchema, metric: dict):
        """将评估分数推送到 Langfuse。

        Args:
            trace: 要评分的 trace。
            score: 评估分数。
            metric: 用于评估的指标。
        """
        self.langfuse.create_score(
            trace_id=trace.id,
            name=metric["name"],
            data_type="NUMERIC",
            value=score.score,
            comment=score.reasoning,
        )

    async def _run_metric_evaluation(self, metric: dict, input: str, output: str) -> ScoreSchema | None:
        """用某个指标对单条 trace 进行评估。

        Args:
            metric: 用于评估的指标定义。
            input: 要评估的输入内容。
            output: 要评估的输出内容。

        Returns:
            包含评估结果的 ScoreSchema，如果评估失败则返回 None。
        """
        metric_name = metric["name"]
        if not metric:
            logger.error(f"Metric {metric_name} not found")
            return None
        system_metric_prompt = metric["prompt"]

        if not input or not output:
            logger.error(f"Metric {metric_name} evaluation failed", input=input, output=output)
            return None
        score = await self._call_openai(system_metric_prompt, input, output)
        if score:
            logger.info(f"Metric {metric_name} evaluation completed successfully", score=score)
        else:
            logger.error(f"Metric {metric_name} evaluation failed")
        return score

    async def _call_openai(self, metric_system_prompt: str, input: str, output: str) -> ScoreSchema | None:
        """调用 OpenAI API 来评估一条 trace。

        Args:
            metric_system_prompt: 定义评估指标的系统提示词。
            input: 格式化后的输入消息。
            output: 格式化后的输出消息。

        Returns:
            包含评估结果的 ScoreSchema，如果 API 调用失败则返回 None。
        """
        num_retries = 3
        for _ in range(num_retries):
            try:
                response = await self.client.beta.chat.completions.parse(
                    model=settings.EVALUATION_LLM,
                    messages=[
                        {"role": "system", "content": metric_system_prompt},
                        {"role": "user", "content": f"Input: {input}\nGeneration: {output}"},
                    ],
                    response_format=ScoreSchema,
                )
                return response.choices[0].message.parsed
            except Exception as e:
                SLEEP_TIME = 10
                logger.error("Error calling OpenAI", error=str(e), sleep_time=SLEEP_TIME)
                sleep(SLEEP_TIME)
                continue
        return None

    def __fetch_traces(self) -> list[TraceWithDetails]:
        """获取过去 24 小时内还没有评分的 trace。

        Returns:
            尚未被评分的 trace 列表。
        """
        last_24_hours = datetime.now() - timedelta(hours=24)
        logger.info("fetching_langfuse_traces", from_timestamp=str(last_24_hours))
        try:
            traces = self.langfuse.api.trace.list(
                from_timestamp=last_24_hours, order_by="timestamp.asc", limit=100
            ).data
            traces_without_scores = [trace for trace in traces if not trace.scores]
            return traces_without_scores
        except Exception as e:
            logger.error("Error fetching traces", error=str(e))
            return []
