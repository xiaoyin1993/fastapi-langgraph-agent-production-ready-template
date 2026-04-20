"""用于 LangGraph 的终端命令执行工具。

本模块提供了一个可以与 LangGraph 配合使用的终端工具，
在本地环境异步执行 Shell 命令。包含危险命令拦截、工作目录校验、
超时控制、输出截断与 ANSI 转义剥离等安全与体验优化。
"""

import asyncio
import json
import os
import re

from langchain_core.tools import tool

from app.infrastructure.logging import logger


FOREGROUND_MAX_TIMEOUT: int = int(os.getenv("TERMINAL_MAX_FOREGROUND_TIMEOUT", "600"))
DEFAULT_TIMEOUT: int = int(os.getenv("TERMINAL_TIMEOUT", "180"))
MAX_OUTPUT_CHARS: int = 50_000

# 工作目录的安全字符白名单：允许字母数字、路径分隔符、点号、横杠、下划线、
# 空格、加号、@、=、,、~ 等常见路径字符；其他一律拒绝以阻断 Shell 注入。
_WORKDIR_SAFE_RE = re.compile(r"^[A-Za-z0-9/\\:_\-.~ +@=,]+$")

# ANSI 转义序列剥离正则
_ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# 危险命令模式（基础保护，避免误伤合法操作）
_DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)?(-[a-zA-Z]*f[a-zA-Z]*\s+)?/(\s|$)"), "递归删除根目录"),
    (re.compile(r"\brm\s+-rf?\s+/\*"), "递归删除根目录下所有内容"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;:"), "fork 炸弹"),
    (re.compile(r"\bmkfs\.[a-z0-9]+\b"), "格式化文件系统"),
    (re.compile(r"\bdd\b.*\bof=/dev/(sd|nvme|hd)"), "向块设备写入数据"),
    (re.compile(r">\s*/dev/sd[a-z]"), "覆盖块设备"),
    (re.compile(r"\bshutdown\b|\breboot\b|\bhalt\b|\bpoweroff\b"), "关机或重启系统"),
]


def _validate_workdir(workdir: str) -> str | None:
    """校验工作目录是否包含危险字符。

    Returns:
        None 表示安全，否则返回错误描述。
    """
    if not workdir:
        return None
    if not _WORKDIR_SAFE_RE.match(workdir):
        for ch in workdir:
            if not _WORKDIR_SAFE_RE.match(ch):
                return f"工作目录包含非法字符 {ch!r}，请使用不含 Shell 元字符的简单路径。"
        return "工作目录包含非法字符。"
    return None


def _check_dangerous_command(command: str) -> str | None:
    """检测危险命令。返回危险描述，安全则返回 None。"""
    for pattern, description in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            return description
    return None


def _strip_ansi(text: str) -> str:
    """剥离 ANSI 转义序列，避免污染模型上下文。"""
    return _ANSI_ESCAPE_RE.sub("", text)


def _truncate_output(output: str) -> str:
    """对超长输出做头尾截断保留，避免一次性返回过多内容。"""
    if len(output) <= MAX_OUTPUT_CHARS:
        return output
    head_chars = int(MAX_OUTPUT_CHARS * 0.4)
    tail_chars = MAX_OUTPUT_CHARS - head_chars
    omitted = len(output) - head_chars - tail_chars
    notice = f"\n\n... [输出已截断 - 省略 {omitted} 字符 / 总长 {len(output)}] ...\n\n"
    return output[:head_chars] + notice + output[-tail_chars:]


def _interpret_exit_code(command: str, exit_code: int) -> str | None:
    """对常见的非错误退出码给出说明，避免模型误判失败。"""
    if exit_code == 0:
        return None

    segments = re.split(r"\s*(?:\|\||&&|[|;])\s*", command)
    last_segment = (segments[-1] if segments else command).strip()
    base_cmd = ""
    for word in last_segment.split():
        if "=" in word and not word.startswith("-"):
            continue
        base_cmd = word.split("/")[-1]
        break

    semantics: dict[str, dict[int, str]] = {
        "grep": {1: "未匹配到结果（不是错误）"},
        "egrep": {1: "未匹配到结果（不是错误）"},
        "fgrep": {1: "未匹配到结果（不是错误）"},
        "rg": {1: "未匹配到结果（不是错误）"},
        "diff": {1: "文件存在差异（预期行为，不是错误）"},
        "find": {1: "部分目录无访问权限（结果可能仍然有效）"},
        "test": {1: "条件判断为假（预期行为，不是错误）"},
        "git": {1: "非零退出（通常正常，例如 git diff 在有差异时返回 1）"},
    }
    return semantics.get(base_cmd, {}).get(exit_code)


@tool
async def terminal_tool(
    command: str,
    timeout: int | None = None,
    workdir: str | None = None,
) -> str:
    """在本地环境执行 Shell 命令并返回结果。

    适用于构建、安装、git、脚本运行、网络请求、包管理等需要 Shell 的场景。
    不要使用 cat/head/tail 读取文件，不要使用 vim/nano 等交互式工具。

    Args:
        command: 要执行的 Shell 命令。
        timeout: 命令执行超时时间（秒），默认 180 秒，最大 600 秒。
        workdir: 命令执行的工作目录（绝对路径），默认当前进程工作目录。

    Returns:
        JSON 字符串，包含 output、exit_code、error 等字段。
    """
    if not isinstance(command, str) or not command.strip():
        return json.dumps(
            {"output": "", "exit_code": -1, "error": "命令必须是非空字符串", "status": "error"},
            ensure_ascii=False,
        )

    effective_timeout = timeout or DEFAULT_TIMEOUT
    if effective_timeout > FOREGROUND_MAX_TIMEOUT:
        return json.dumps(
            {
                "output": "",
                "exit_code": -1,
                "error": f"超时时间 {effective_timeout}s 超过最大值 {FOREGROUND_MAX_TIMEOUT}s",
                "status": "error",
            },
            ensure_ascii=False,
        )

    danger = _check_dangerous_command(command)
    if danger:
        logger.warning("terminal_command_blocked", reason=danger, command=command[:200])
        return json.dumps(
            {"output": "", "exit_code": -1, "error": f"命令被拒绝：{danger}", "status": "blocked"},
            ensure_ascii=False,
        )

    if workdir:
        workdir_error = _validate_workdir(workdir)
        if workdir_error:
            logger.warning("terminal_workdir_blocked", workdir=workdir[:200])
            return json.dumps(
                {"output": "", "exit_code": -1, "error": workdir_error, "status": "blocked"},
                ensure_ascii=False,
            )
        if not os.path.isdir(workdir):
            return json.dumps(
                {"output": "", "exit_code": -1, "error": f"工作目录不存在：{workdir}", "status": "error"},
                ensure_ascii=False,
            )

    logger.info(
        "terminal_command_started",
        command=command[:200],
        workdir=workdir or os.getcwd(),
        timeout=effective_timeout,
    )

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=workdir or None,
        )
    except Exception as exc:
        logger.exception("terminal_command_spawn_failed", command=command[:200])
        return json.dumps(
            {
                "output": "",
                "exit_code": -1,
                "error": f"命令启动失败：{type(exc).__name__}: {exc}",
                "status": "error",
            },
            ensure_ascii=False,
        )

    try:
        stdout_bytes, _ = await asyncio.wait_for(process.communicate(), timeout=effective_timeout)
    except asyncio.TimeoutError:
        try:
            process.kill()
            await process.wait()
        except ProcessLookupError:
            pass
        logger.warning("terminal_command_timeout", command=command[:200], timeout=effective_timeout)
        return json.dumps(
            {
                "output": "",
                "exit_code": 124,
                "error": f"命令超时（{effective_timeout} 秒）",
                "status": "timeout",
            },
            ensure_ascii=False,
        )

    output = stdout_bytes.decode("utf-8", errors="replace")
    output = _strip_ansi(output)
    output = _truncate_output(output.strip())
    returncode = process.returncode if process.returncode is not None else -1

    result: dict[str, object] = {
        "output": output,
        "exit_code": returncode,
        "error": None,
    }
    exit_note = _interpret_exit_code(command, returncode)
    if exit_note:
        result["exit_code_meaning"] = exit_note

    logger.info(
        "terminal_command_finished",
        command=command[:200],
        exit_code=returncode,
        output_length=len(output),
    )
    return json.dumps(result, ensure_ascii=False)
