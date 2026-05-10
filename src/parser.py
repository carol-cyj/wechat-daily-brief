"""
文章解析模块
负责从 HTML 页面中提取文章正文内容
使用微信 UA 伪装获取微信公众号文章全文
支持评论区高赞内容抓取
"""

import logging
import re
import json
from typing import Optional, List, Dict

import requests
from bs4 import BeautifulSoup

from .utils import clean_text

logger = logging.getLogger(__name__)

# 微信客户端 User-Agent（关键：必须包含 MicroMessenger 才能获取完整内容）
WECHAT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Mobile/15E148 MicroMessenger/8.0.34(0x16082222) "
    "NetType/WIFI Language/zh_CN"
)

# 通用浏览器 UA（非微信页面的备用）
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class Article:
    """文章数据结构"""
    def __init__(self, title: str, url: str, source: str, category: str,
                 category_name: str, content: str = "", summary: str = "",
                 publish_date: str = "", fetch_method: str = "",
                 importance: int = 5, top_comments: List[Dict] = None):
        self.title = title
        self.url = url
        self.source = source
        self.category = category
        self.category_name = category_name
        self.content = content
        self.summary = summary
        self.publish_date = publish_date
        self.fetch_method = fetch_method
        self.importance = importance
        self.top_comments = top_comments or []  # 高赞评论列表
        self.angle_title = ""  # 角度小标题（如"估值逻辑转向"、"裁员与扁平化"）
        self.difficulty = "进阶"
        self.terms = []

    @property
    def content_hash(self) -> str:
        """用于去重的哈希值"""
        from .utils import generate_hash
        return generate_hash(self.title + self.url)


class ArticleParser:
    """
    文章解析器
    从微信公众号文章页面提取正文
    核心策略：使用微信客户端 UA 伪装，服务器直接返回完整 HTML
    """

    def __init__(self, timeout: int = 15, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()

    def parse_article(self, url: str, source: str = "", category: str = "",
                      category_name: str = "", fetch_method: str = "") -> Optional[Article]:
        """
        解析单篇文章

        Args:
            url: 文章 URL
            source: 公众号名称
            category: 内容方向 key
            category_name: 内容方向名称
            fetch_method: 抓取方式

        Returns:
            Article 对象，解析失败返回 None
        """
        try:
            html = self._fetch_html(url)
            if not html:
                logger.warning(f"无法获取文章内容: {url}")
                return None

            title, content, publish_date = self._extract_content(html)
            if not title:
                logger.warning(f"无法提取标题: {url}")
                return None

            return Article(
                title=clean_text(title),
                url=url,
                source=source,
                category=category,
                category_name=category_name,
                content=clean_text(content),
                publish_date=publish_date,
                fetch_method=fetch_method,
            )
        except Exception as e:
            logger.error(f"解析文章失败 [{url}]: {e}")
            return None

    def _fetch_html(self, url: str) -> Optional[str]:
        """
        获取页面 HTML
        微信文章使用微信 UA，其他页面使用浏览器 UA
        """
        is_wechat = "mp.weixin.qq.com" in url or "weixin" in url
        ua = WECHAT_UA if is_wechat else BROWSER_UA

        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(
                    url, timeout=self.timeout,
                    allow_redirects=True, headers=headers,
                )
                resp.raise_for_status()
                if resp.encoding and resp.encoding.lower() != "utf-8":
                    resp.encoding = resp.apparent_encoding or "utf-8"
                return resp.text
            except requests.RequestException as e:
                logger.warning(f"请求失败 (第{attempt + 1}次) [{url}]: {e}")
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)
        return None

    def _extract_content(self, html: str) -> tuple:
        """
        从 HTML 中提取标题、正文、发布日期
        针对微信公众号文章页面优化
        """
        soup = BeautifulSoup(html, "lxml")

        # ===== 提取标题 =====
        title = ""
        title_tag = (soup.select_one("#activity-name")
                     or soup.select_one("h1.rich_media_title"))
        if title_tag:
            title = title_tag.get_text(strip=True)
        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True).split(" - ")[0].split("_")[0].strip()

        # ===== 提取正文 =====
        content = ""
        # 微信公众号文章正文（优先）
        content_div = (soup.select_one("#js_content")
                       or soup.select_one(".rich_media_content"))
        if content_div:
            for tag in content_div.find_all(["script", "style", "iframe"]):
                tag.decompose()
            content = content_div.get_text(separator="\n", strip=True)

        # 通用正文提取（非微信页面）
        if not content:
            try:
                from readability import Document
                doc = Document(html)
                content_soup = BeautifulSoup(doc.summary(), "lxml")
                for tag in content_soup.find_all(["script", "style"]):
                    tag.decompose()
                content = content_soup.get_text(separator="\n", strip=True)
            except ImportError:
                pass

        if not content:
            paragraphs = soup.find_all("p")
            texts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
            content = "\n".join(texts)

        # ===== 提取发布日期 =====
        publish_date = ""
        date_tag = (soup.select_one("#publish_time")
                    or soup.select_one(".rich_media_meta_primary_text"))
        if date_tag:
            publish_date = date_tag.get_text(strip=True)
        if not publish_date:
            meta_date = soup.find("meta", attrs={"property": "article:published_time"})
            if meta_date:
                publish_date = meta_date.get("content", "")
            else:
                meta_date = soup.find("meta", attrs={"name": "publishdate"})
                if meta_date:
                    publish_date = meta_date.get("content", "")

        return title, content, publish_date

    def fetch_comments(self, url: str, html: str = None) -> List[Dict]:
        """
        抓取文章评论区高赞内容
        
        微信公众号评论区需要特殊处理：
        1. 评论数据通过 AJAX 接口加载
        2. 需要从页面提取 comment_id 和其他参数
        3. 调用评论接口获取数据
        
        Args:
            url: 文章 URL
            html: 已获取的 HTML（可选，避免重复请求）
            
        Returns:
            高赞评论列表，每项包含 {author, content, likes}
        """
        comments = []
        
        try:
            # 如果没有传入 HTML，先获取页面
            if not html:
                html = self._fetch_html(url)
            if not html:
                return comments
            
            # 从页面提取评论相关参数
            params = self._extract_comment_params(html)
            if not params:
                logger.debug(f"未找到评论参数: {url}")
                return comments
            
            # 调用评论接口
            comments = self._fetch_comments_api(url, params)
            
        except Exception as e:
            logger.warning(f"获取评论失败 [{url}]: {e}")
        
        return comments[:3]  # 只返回前3条高赞
    
    def _extract_comment_params(self, html: str) -> Optional[Dict]:
        """
        从页面 HTML 中提取评论接口所需的参数
        
        微信评论接口需要以下参数：
        - comment_id: 文章评论 ID
        - appmsgid: 文章 ID
        - itemidx: 文章索引
        """
        params = {}
        
        # 方法1: 从 JavaScript 变量中提取
        # 常见模式: var comment_id = "123456" 或 comment_id = "123456"
        patterns = {
            'comment_id': [
                r'var\s+comment_id\s*=\s*["\']?(\d+)["\']?',
                r'comment_id\s*=\s*["\']?(\d+)["\']?',
                r'"comment_id"\s*:\s*"?(\d+)"?',
            ],
            'appmsgid': [
                r'var\s+appmsgid\s*=\s*["\']?(\d+)["\']?',
                r'appmsgid\s*=\s*["\']?(\d+)["\']?',
                r'"appmsgid"\s*:\s*"?(\d+)"?',
            ],
            'itemidx': [
                r'var\s+itemidx\s*=\s*["\']?(\d+)["\']?',
                r'itemidx\s*=\s*["\']?(\d+)["\']?',
                r'"itemidx"\s*:\s*"?(\d+)"?',
            ],
        }
        
        for key, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, html)
                if match:
                    params[key] = match.group(1)
                    break
        
        # 必须有 comment_id 才能获取评论
        if not params.get('comment_id'):
            # 尝试从 meta 标签获取
            soup = BeautifulSoup(html, "lxml")
            meta = soup.find('meta', attrs={'name': 'comment_id'})
            if meta and meta.get('content'):
                params['comment_id'] = meta.get('content')
        
        return params if params.get('comment_id') else None
    
    def _fetch_comments_api(self, article_url: str, params: Dict) -> List[Dict]:
        """
        调用微信评论接口获取评论数据
        
        微信评论接口：
        https://mp.weixin.qq.com/mp/appmsg_comment?action=getcomment&...
        """
        comments = []
        
        comment_id = params.get('comment_id')
        if not comment_id:
            return comments
        
        # 构建评论接口 URL
        api_url = "https://mp.weixin.qq.com/mp/appmsg_comment"
        
        query_params = {
            'action': 'getcomment',
            'comment_id': comment_id,
            'appmsgid': params.get('appmsgid', ''),
            'itemidx': params.get('itemidx', '1'),
            'offset': '0',
            'limit': '10',  # 获取更多，后面按点赞排序
            'f': 'json',
        }
        
        headers = {
            'User-Agent': WECHAT_UA,
            'Referer': article_url,
            'Accept': 'application/json, text/plain, */*',
        }
        
        try:
            resp = self.session.get(
                api_url,
                params=query_params,
                headers=headers,
                timeout=self.timeout,
            )
            
            if resp.status_code != 200:
                return comments
            
            data = resp.json()
            
            # 解析评论数据
            if data.get('base_resp', {}).get('ret') == 0:
                elected_comment = data.get('elected_comment', [])
                
                for item in elected_comment:
                    comment = {
                        'author': item.get('nick_name', '匿名'),
                        'content': item.get('content', ''),
                        'likes': item.get('like_num', 0),
                    }
                    if comment['content']:
                        comments.append(comment)
                
                # 按点赞数排序，取前3条高赞
                comments.sort(key=lambda x: x['likes'], reverse=True)
                
        except Exception as e:
            logger.debug(f"评论接口请求失败: {e}")
        
        return comments
