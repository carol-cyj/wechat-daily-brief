"""
语音合成模块
支持 Edge TTS（免费）和 OpenAI TTS（付费）
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional

from .config import TTSConfig
from .utils import format_duration

logger = logging.getLogger(__name__)


class TTSEngine:
    """
    语音合成引擎
    """

    def __init__(self, config: TTSConfig):
        self.config = config

    def synthesize(self, text: str, output_path: str) -> bool:
        """
        将文本合成为语音文件

        Args:
            text: 要合成的文本
            output_path: 输出文件路径（.mp3）

        Returns:
            是否成功
        """
        if self.config.provider == "edge":
            return self._synthesize_edge(text, output_path)
        elif self.config.provider == "openai":
            return self._synthesize_openai(text, output_path)
        else:
            logger.error(f"不支持的 TTS 提供商: {self.config.provider}")
            return False

    def _synthesize_edge(self, text: str, output_path: str) -> bool:
        """
        使用 Edge TTS 合成语音（免费）

        Args:
            text: 文本内容
            output_path: 输出路径

        Returns:
            是否成功
        """
        try:
            import edge_tts
        except ImportError:
            logger.error("请安装 edge-tts: pip install edge-tts")
            return False

        voice = self.config.edge.voice
        rate = self.config.edge.rate
        volume = self.config.edge.volume

        logger.info(f"使用 Edge TTS 合成语音 (voice={voice})...")

        try:
            # 使用 asyncio 运行 edge_tts
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate,
                volume=volume,
            )

            # 确保输出目录存在
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            loop.run_until_complete(
                communicate.save(output_path)
            )
            loop.close()

            # 检查文件大小
            file_size = Path(output_path).stat().st_size
            if file_size > 0:
                logger.info(f"语音合成成功: {output_path} ({file_size / 1024:.1f} KB)")
                return True
            else:
                logger.error("语音文件为空")
                return False

        except Exception as e:
            logger.error(f"Edge TTS 合成失败: {e}")
            return False

    def _synthesize_openai(self, text: str, output_path: str) -> bool:
        """
        使用 OpenAI TTS 合成语音（付费）

        Args:
            text: 文本内容
            output_path: 输出路径

        Returns:
            是否成功
        """
        try:
            from openai import OpenAI
        except ImportError:
            logger.error("请安装 openai: pip install openai")
            return False

        api_key = self.config.openai.api_key
        model = self.config.openai.model
        voice = self.config.openai.voice

        if not api_key:
            logger.error("OpenAI TTS 需要 API Key，请在配置中设置 tts.openai.api_key")
            return False

        logger.info(f"使用 OpenAI TTS 合成语音 (model={model}, voice={voice})...")

        try:
            client = OpenAI(api_key=api_key)

            # 确保输出目录存在
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            response = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
            )

            response.stream_to_file(output_path)

            file_size = Path(output_path).stat().st_size
            if file_size > 0:
                logger.info(f"语音合成成功: {output_path} ({file_size / 1024:.1f} KB)")
                return True
            else:
                logger.error("语音文件为空")
                return False

        except Exception as e:
            logger.error(f"OpenAI TTS 合成失败: {e}")
            return False


def build_brief_script(articles, trend_comment: str, date_str: str) -> str:
    """
    构建适合语音播报的简报脚本

    Args:
        articles: 核心文章列表
        trend_comment: 趋势点评
        date_str: 日期字符串

    Returns:
        播报脚本文本
    """
    lines = []

    # 开场白
    lines.append(f"早上好，这里是今日资讯简报，{date_str}。")
    lines.append("")
    lines.append("以下是今天最值得关注的资讯：")
    lines.append("")

    # 逐条播报
    for i, article in enumerate(articles, 1):
        direction = article.category_name
        title = article.title
        summary = article.summary or ""

        lines.append(f"第{i}条，{direction}。")
        lines.append(f"{title}。")
        if summary:
            lines.append(f"{summary}。")
        lines.append(f"来源：{article.source}。")
        lines.append("")

    # 趋势点评
    if trend_comment:
        lines.append("以上是今日核心资讯。")
        lines.append("")
        lines.append("今日趋势点评：")
        lines.append(trend_comment)
        lines.append("")

    # 结束语
    lines.append("以上就是今天的全部资讯，祝你通勤愉快！")

    return "\n".join(lines)
