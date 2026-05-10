"""
配置管理模块
负责加载、验证和管理 YAML 配置文件
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class AccountConfig:
    """单个公众号账号配置"""
    name: str
    rss_url: str = ""
    manual_urls: List[str] = field(default_factory=list)


@dataclass
class CategoryConfig:
    """内容方向配置"""
    key: str
    name: str
    description: str = ""
    accounts: List[AccountConfig] = field(default_factory=list)


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "openai"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    max_tokens: int = 2000
    temperature: float = 0.3


@dataclass
class EdgeTTSConfig:
    """Edge TTS 配置"""
    voice: str = "zh-CN-YunxiNeural"
    rate: str = "+5%"
    volume: str = "+0%"


@dataclass
class OpenAITTSConfig:
    """OpenAI TTS 配置"""
    api_key: str = ""
    model: str = "tts-1"
    voice: str = "alloy"


@dataclass
class TTSConfig:
    """TTS 总配置"""
    provider: str = "edge"
    edge: EdgeTTSConfig = field(default_factory=EdgeTTSConfig)
    openai: OpenAITTSConfig = field(default_factory=OpenAITTSConfig)


@dataclass
class FetcherConfig:
    """抓取器配置"""
    max_articles_per_account: int = 5
    timeout: int = 15
    delay: float = 2.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    max_retries: int = 3


@dataclass
class BriefConfig:
    """简报配置"""
    top_n: int = 7
    min_per_category: int = 1
    output_format: str = "markdown"


@dataclass
class OutputConfig:
    """输出配置"""
    dir: str = "./output"
    text_filename: str = "{date}_brief.md"
    audio_filename: str = "{date}_brief.mp3"


@dataclass
class AppConfig:
    """应用总配置"""
    categories: Dict[str, CategoryConfig] = field(default_factory=dict)
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    fetcher: FetcherConfig = field(default_factory=FetcherConfig)
    brief: BriefConfig = field(default_factory=BriefConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    config_path: str = ""
    # WeWe-RSS 数据源配置
    wewe_base_url: str = ""
    wewe_auth_code: str = ""


def load_config(config_path: str) -> AppConfig:
    """
    从 YAML 文件加载配置

    Args:
        config_path: 配置文件路径

    Returns:
        AppConfig 实例

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置格式错误
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw:
        raise ValueError("配置文件为空")

    # 解析公众号分类
    categories = {}
    for cat_key, cat_data in raw.get("categories", {}).items():
        accounts = []
        for acc_data in cat_data.get("accounts", []):
            accounts.append(AccountConfig(
                name=acc_data.get("name", ""),
                rss_url=acc_data.get("rss_url", ""),
                manual_urls=acc_data.get("manual_urls", []),
            ))
        categories[cat_key] = CategoryConfig(
            key=cat_key,
            name=cat_data.get("name", cat_key),
            description=cat_data.get("description", ""),
            accounts=accounts,
        )

    # 解析数据源配置
    ds_raw = raw.get("data_source", {})
    wewe_base_url = ds_raw.get("wewe_base_url", "")
    wewe_auth_code = ds_raw.get("wewe_auth_code", "")

    # 解析 LLM 配置
    llm_raw = raw.get("llm", {})
    llm = LLMConfig(
        provider=llm_raw.get("provider", "openai"),
        api_key=llm_raw.get("api_key", ""),
        base_url=llm_raw.get("base_url", "https://api.openai.com/v1"),
        model=llm_raw.get("model", "gpt-4o-mini"),
        max_tokens=llm_raw.get("max_tokens", 2000),
        temperature=llm_raw.get("temperature", 0.3),
    )

    # 解析 TTS 配置
    tts_raw = raw.get("tts", {})
    edge_raw = tts_raw.get("edge", {})
    openai_raw = tts_raw.get("openai", {})
    tts = TTSConfig(
        provider=tts_raw.get("provider", "edge"),
        edge=EdgeTTSConfig(
            voice=edge_raw.get("voice", "zh-CN-YunxiNeural"),
            rate=edge_raw.get("rate", "+5%"),
            volume=edge_raw.get("volume", "+0%"),
        ),
        openai=OpenAITTSConfig(
            api_key=openai_raw.get("api_key", ""),
            model=openai_raw.get("model", "tts-1"),
            voice=openai_raw.get("voice", "alloy"),
        ),
    )

    # 解析抓取配置
    fetch_raw = raw.get("fetcher", {})
    fetcher = FetcherConfig(
        max_articles_per_account=fetch_raw.get("max_articles_per_account", 5),
        timeout=fetch_raw.get("timeout", 15),
        delay=fetch_raw.get("delay", 2.0),
        user_agent=fetch_raw.get("user_agent", FetcherConfig.user_agent),
        max_retries=fetch_raw.get("max_retries", 3),
    )

    # 解析简报配置
    brief_raw = raw.get("brief", {})
    brief = BriefConfig(
        top_n=brief_raw.get("top_n", 7),
        min_per_category=brief_raw.get("min_per_category", 1),
        output_format=brief_raw.get("output_format", "markdown"),
    )

    # 解析输出配置
    output_raw = raw.get("output", {})
    output = OutputConfig(
        dir=output_raw.get("dir", "./output"),
        text_filename=output_raw.get("text_filename", "{date}_brief.md"),
        audio_filename=output_raw.get("audio_filename", "{date}_brief.mp3"),
    )

    return AppConfig(
        categories=categories,
        llm=llm,
        tts=tts,
        fetcher=fetcher,
        brief=brief,
        output=output,
        config_path=str(path),
        wewe_base_url=wewe_base_url,
        wewe_auth_code=wewe_auth_code,
    )


def get_output_paths(config: AppConfig, date_str: str) -> tuple:
    """
    获取输出文件路径

    Args:
        config: 应用配置
        date_str: 日期字符串，如 "2025-01-15"

    Returns:
        (text_path, audio_path) 元组
    """
    output_dir = Path(config.output.dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    text_name = config.output.text_filename.replace("{date}", date_str)
    audio_name = config.output.audio_filename.replace("{date}", date_str)

    return str(output_dir / text_name), str(output_dir / audio_name)
