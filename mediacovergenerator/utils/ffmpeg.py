from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from mediacovergenerator.logging import logger


def resolve_ffmpeg_binary() -> str:
    candidates = [
        os.getenv("MCG_FFMPEG", "").strip(),
        os.getenv("FFMPEG_BINARY", "").strip(),
        shutil.which("ffmpeg") or "",
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    raise RuntimeError("未找到 ffmpeg。请先安装 ffmpeg，或通过环境变量 MCG_FFMPEG 指定可执行文件路径。")


def normalize_animation_reduce_mode(value: object) -> str:
    if isinstance(value, bool):
        return "strong" if value else "off"
    text = str(value or "").strip().lower()
    mapping = {
        "off": "off",
        "low": "medium",
        "medium": "medium",
        "high": "strong",
        "strong": "strong",
    }
    return mapping.get(text, "medium")


def animation_output_suffix(animation_format: str) -> str:
    safe_format = str(animation_format or "").strip().lower()
    if safe_format == "gif":
        return ".gif"
    if safe_format == "webp":
        return ".webp"
    return ".png"


def build_animation_export_command(
    frames_pattern: str | Path,
    fps: int,
    animation_format: str,
    output_file: str | Path,
    reduce_mode: object,
    threads: int = 2,
) -> list[str]:
    ffmpeg_binary = resolve_ffmpeg_binary()
    safe_format = str(animation_format or "").strip().lower()
    safe_mode = normalize_animation_reduce_mode(reduce_mode)
    safe_fps = max(1, int(fps))
    safe_threads = max(1, int(threads))

    common = [
        ffmpeg_binary,
        "-hide_banner",
        "-y",
        "-framerate",
        str(safe_fps),
        "-i",
        str(frames_pattern),
        "-threads",
        str(safe_threads),
    ]

    if safe_format == "gif":
        palette_colors = "64" if safe_mode == "strong" else ("128" if safe_mode == "medium" else "256")
        palette_dither = "none" if safe_mode == "strong" else ("bayer:bayer_scale=3" if safe_mode == "medium" else "floyd_steinberg")
        return common + [
            "-filter_complex",
            f"[0:v]split[a][b];[a]palettegen=max_colors={palette_colors}[p];[b][p]paletteuse=dither={palette_dither}",
            "-loop",
            "0",
            "-f",
            "gif",
            str(output_file),
        ]

    if safe_format == "webp":
        quality = "68" if safe_mode == "strong" else ("80" if safe_mode == "medium" else "92")
        compression = "6" if safe_mode == "strong" else ("5" if safe_mode == "medium" else "4")
        return common + [
            "-c:v",
            "libwebp_anim",
            "-pix_fmt",
            "yuva420p",
            "-loop",
            "0",
            "-quality",
            quality,
            "-compression_level",
            compression,
            "-f",
            "webp",
            str(output_file),
        ]

    compression = "9" if safe_mode == "strong" else ("6" if safe_mode == "medium" else "3")
    return common + [
        "-vcodec",
        "apng",
        "-pix_fmt",
        "rgba",
        "-plays",
        "0",
        "-pred",
        "mixed",
        "-compression_level",
        compression,
        "-f",
        "apng",
        str(output_file),
    ]


def run_ffmpeg(command: list[str], stop_event=None, timeout_seconds: int = 180, label: str = "ffmpeg") -> bool:
    if not command:
        raise RuntimeError("ffmpeg 命令为空")

    popen_kwargs = {
        "args": command,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "text": False,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    start_time = time.monotonic()
    logger.info("开始执行 %s", label)

    with tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(stderr=stderr_file, **popen_kwargs)
        try:
            while True:
                return_code = process.poll()
                if return_code is not None:
                    break

                if stop_event and stop_event.is_set():
                    logger.info("检测到停止信号，正在终止 %s", label)
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
                    return False

                if time.monotonic() - start_time > timeout_seconds:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
                    stderr_tail = _read_stderr_tail(stderr_file)
                    raise TimeoutError(f"{label} 执行超时（>{timeout_seconds} 秒）。{stderr_tail}")

                time.sleep(0.1)

            if return_code != 0:
                stderr_tail = _read_stderr_tail(stderr_file)
                raise RuntimeError(f"{label} 执行失败（退出码 {return_code}）。{stderr_tail}")

            stderr_tail = _read_stderr_tail(stderr_file)
            if stderr_tail:
                logger.debug("%s 输出: %s", label, stderr_tail)
            logger.info("%s 执行完成", label)
            return True
        finally:
            if process.poll() is None:
                process.kill()


def _read_stderr_tail(stderr_file, limit: int = 12000) -> str:
    stderr_file.seek(0, os.SEEK_END)
    size = stderr_file.tell()
    stderr_file.seek(max(0, size - limit), os.SEEK_SET)
    data = stderr_file.read()
    if not data:
        return ""
    return data.decode("utf-8", "ignore").strip()
