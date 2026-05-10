"""
数据抓取模块
实现多策略数据源：WeWe-RSS API + 通用 RSS + 手动 URL
"""

import logging
import time
from typing import Dict, List, Optional

import feedparser
import requests

from .config import AccountConfig, CategoryConfig, FetcherConfig
from .parser import Article, ArticleParser
from .utils import clean_text

logger = logging.getLogger(__name__)


class WeWeRSSFetcher:
    """
    WeWe-RSS 抓取器
    通过自部署的 WeWe-RSS 服务获取公众号文章 RSS

    WeWe-RSS 是基于微信读书接口的开源工具，
    Docker 一键部署，自动定时更新公众号文章。
    GitHub: https://github.com/cooderl/wewe-rss
    """

    def __init__(self, config: FetcherConfig, wewe_base_url: str = "",
                 wewe_auth_code: str = ""):
        self.config = config
        self.wewe_base_url = wewe_base_url.rstrip("/")
        self.wewe_auth_code = wewe_auth_code

    def fetch_articles(self, account: AccountConfig, category: CategoryConfig,
                       max_articles: int = 5) -> List[Article]:
        """
        通过 WeWe-RSS 获取公众号文章

        Args:
            account: 公众号配置（使用 rss_url 字段存放 WeWe-RSS 的 RSS 地址）
            category: 内容方向配置
            max_articles: 最大文章数

        Returns:
            文章列表
        """
        if not self.wewe_base_url:
            return []

        articles = []

        # 构建请求 URL
        # WeWe-RSS 提供 RSS 端点: {base_url}/feed/{auth_code}
        # 如果 account 配置了 rss_url，直接使用
        rss_url = account.rss_url
        if not rss_url and self.wewe_base_url:
            # 尝试通过 API 搜索公众号
            rss_url = self._search_account_feed(account.name)

        if not rss_url:
            return []

        try:
            feed = feedparser.parse(rss_url)

            if feed.bozo and not feed.entries:
                logger.warning(f"WeWe-RSS 解析失败 [{account.name}]: {feed.bozo_exception}")
                return articles

            for entry in feed.entries[:max_articles]:
                title = entry.get("title", "")
                url = entry.get("link", "")
                if not title or not url:
                    continue

                publish_date = ""
                if "published" in entry:
                    publish_date = entry.published
                elif "updated" in entry:
                    publish_date = entry.updated

                articles.append(Article(
                    title=clean_text(title),
                    url=url,
                    source=account.name,
                    category=category.key,
                    category_name=category.name,
                    publish_date=publish_date,
                    fetch_method="wewe-rss",
                ))

            logger.info(f"WeWe-RSS 获取到 {len(articles)} 篇文章 [{account.name}]")

        except Exception as e:
            logger.error(f"WeWe-RSS 抓取异常 [{account.name}]: {e}")

        return articles

    def _search_account_feed(self, account_name: str) -> Optional[str]:
        """
        通过 WeWe-RSS API 搜索公众号并获取 RSS 地址

        Args:
            account_name: 公众号名称

        Returns:
            RSS URL 或 None
        """
        if not self.wewe_base_url:
            return None

        try:
            # WeWe-RSS 提供搜索 API
            search_url = f"{self.wewe_base_url}/api/feed/search"
            params = {
                "keyword": account_name,
                "auth_code": self.wewe_auth_code,
            }
            headers = {"Accept": "application/json"}

            resp = requests.get(
                search_url, params=params, headers=headers,
                timeout=self.config.timeout,
            )

            if resp.status_code == 200:
                data = resp.json()
                # 根据返回结果构建 RSS URL
                if isinstance(data, dict) and data.get("data"):
                    feeds = data["data"]
                    if isinstance(feeds, list) and len(feeds) > 0:
                        feed_id = feeds[0].get("id", "")
                        if feed_id:
                            return f"{self.wewe_base_url}/feed/{feed_id}"

            logger.debug(f"WeWe-RSS 搜索未找到 [{account_name}]")
            return None

        except Exception as e:
            logger.debug(f"WeWe-RSS 搜索异常 [{account_name}]: {e}")
            return None


class RSSFetcher:
    """
    通用 RSS 订阅抓取器
    支持任何标准 RSS/Atom 源
    """

    def __init__(self, config: FetcherConfig):
        self.config = config

    def fetch_articles(self, account: AccountConfig, category: CategoryConfig,
                       max_articles: int = 5) -> List[Article]:
        """
        通过 RSS 获取公众号文章

        Args:
            account: 公众号配置
            category: 内容方向配置
            max_articles: 最大文章数

        Returns:
            文章列表
        """
        articles = []
        rss_url = account.rss_url

        if not rss_url:
            return articles

        try:
            feed = feedparser.parse(rss_url)

            if feed.bozo and not feed.entries:
                logger.warning(f"RSS 解析失败 [{account.name}]: {feed.bozo_exception}")
                return articles

            for entry in feed.entries[:max_articles]:
                title = entry.get("title", "")
                url = entry.get("link", "")
                if not title or not url:
                    continue

                publish_date = ""
                if "published" in entry:
                    publish_date = entry.published
                elif "updated" in entry:
                    publish_date = entry.updated

                articles.append(Article(
                    title=clean_text(title),
                    url=url,
                    source=account.name,
                    category=category.key,
                    category_name=category.name,
                    publish_date=publish_date,
                    fetch_method="rss",
                ))

            logger.info(f"RSS 获取到 {len(articles)} 篇文章 [{account.name}]")

        except Exception as e:
            logger.error(f"RSS 抓取异常 [{account.name}]: {e}")

        return articles


class ManualURLFetcher:
    """
    手动 URL 抓取器
    直接使用用户配置的文章 URL（适合临时补充）
    """

    def __init__(self, config: FetcherConfig):
        self.config = config

    def fetch_articles(self, account: AccountConfig, category: CategoryConfig) -> List[Article]:
        """
        从手动配置的 URL 创建文章对象

        Args:
            account: 公众号配置
            category: 内容方向配置

        Returns:
            文章列表
        """
        articles = []
        for url in account.manual_urls:
            if url.strip():
                articles.append(Article(
                    title="",
                    url=url.strip(),
                    source=account.name,
                    category=category.key,
                    category_name=category.name,
                    fetch_method="manual",
                ))

        if articles:
            logger.info(f"手动 URL 加载 {len(articles)} 篇文章 [{account.name}]")

        return articles


class ArticleFetcher:
    """
    统一文章抓取器
    整合多种数据源策略，优先级：WeWe-RSS > 通用 RSS > 手动 URL
    """

    def __init__(self, config: FetcherConfig, wewe_base_url: str = "",
                 wewe_auth_code: str = ""):
        self.config = config
        self.wewe_fetcher = WeWeRSSFetcher(config, wewe_base_url, wewe_auth_code)
        self.rss_fetcher = RSSFetcher(config)
        self.manual_fetcher = ManualURLFetcher(config)
        self.parser = ArticleParser(
            timeout=config.timeout,
            max_retries=config.max_retries,
        )

    def fetch_all(self, categories: Dict[str, CategoryConfig]) -> List[Article]:
        """
        抓取所有配置的公众号文章

        Args:
            categories: 内容方向配置字典

        Returns:
            所有文章列表（去重后）
        """
        all_articles = []
        seen_hashes = set()

        for cat_key, category in categories.items():
            logger.info(f"开始抓取 [{category.name}] 方向的文章...")

            for account in category.accounts:
                articles = []

                # 策略1: WeWe-RSS（全自动，最推荐）
                wewe_articles = self.wewe_fetcher.fetch_articles(
                    account, category, self.config.max_articles_per_account
                )
                articles.extend(wewe_articles)

                # 策略2: 通用 RSS（如果 WeWe-RSS 没有结果，且配置了独立 RSS 源）
                if not articles and account.rss_url and not self.wewe_fetcher.wewe_base_url:
                    rss_articles = self.rss_fetcher.fetch_articles(
                        account, category, self.config.max_articles_per_account
                    )
                    articles.extend(rss_articles)

                # 策略3: 手动 URL（兜底补充）
                if account.manual_urls:
                    manual_articles = self.manual_fetcher.fetch_articles(account, category)
                    articles.extend(manual_articles)

                # 去重
                for article in articles:
                    if article.content_hash not in seen_hashes:
                        seen_hashes.add(article.content_hash)
                        all_articles.append(article)

                # 请求间隔
                time.sleep(self.config.delay)

        logger.info(f"共获取 {len(all_articles)} 篇文章（去重后）")
        return all_articles

    def fetch_article_content(self, article: Article, fetch_comments: bool = True) -> Article:
        """
        抓取文章正文内容（使用微信 UA 伪装）
        同时抓取评论区高赞内容

        Args:
            article: 文章对象（需有 URL）
            fetch_comments: 是否抓取评论（默认 True）

        Returns:
            填充了正文内容和评论的文章对象
        """
        parsed = self.parser.parse_article(
            url=article.url,
            source=article.source,
            category=article.category,
            category_name=article.category_name,
            fetch_method=article.fetch_method,
        )

        if parsed:
            if parsed.title and (not article.title or len(parsed.title) > len(article.title)):
                article.title = parsed.title
            article.content = parsed.content
            if parsed.publish_date:
                article.publish_date = parsed.publish_date
            
            # 抓取评论区高赞
            if fetch_comments:
                try:
                    comments = self.parser.fetch_comments(article.url)
                    if comments:
                        article.top_comments = comments
                        logger.info(f"  获取到 {len(comments)} 条高赞评论")
                except Exception as e:
                    logger.debug(f"评论抓取失败: {e}")
        else:
            logger.warning(f"无法解析文章内容: {article.url}")

        return article
