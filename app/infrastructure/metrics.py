"""应用的 Prometheus 监控指标配置。

这个模块负责设置和配置 Prometheus 监控指标，用于监控应用运行状态。
"""

from prometheus_client import Counter, Histogram, Gauge
from starlette_prometheus import metrics, PrometheusMiddleware

# HTTP 请求指标
http_requests_total = Counter("http_requests_total", "Total number of HTTP requests", ["method", "endpoint", "status"])

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "endpoint"]
)

# 数据库指标
db_connections = Gauge("db_connections", "Number of active database connections")

# 自定义业务指标
orders_processed = Counter("orders_processed_total", "Total number of orders processed")

llm_inference_duration_seconds = Histogram(
    "llm_inference_duration_seconds",
    "Time spent processing LLM inference",
    ["model"],
    buckets=[0.1, 0.3, 0.5, 1.0, 2.0, 5.0]
)



llm_stream_duration_seconds = Histogram(
    "llm_stream_duration_seconds",
    "Time spent processing LLM stream inference",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)


def setup_metrics(app):
    """配置 Prometheus 监控中间件和指标端点。

    Args:
        app: FastAPI 应用实例
    """
    # 添加 Prometheus 中间件
    app.add_middleware(PrometheusMiddleware)

    # 添加指标端点
    app.add_route("/metrics", metrics)
