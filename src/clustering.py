"""
文章聚类模块
使用 LLM 对文章进行主题聚类，识别同类文章并分组
"""

import logging
from typing import Dict, List, Set, Tuple
from collections import defaultdict

from .parser import Article
from .config import LLMConfig
from openai import OpenAI
import json

logger = logging.getLogger(__name__)


class ArticleCluster:
    """文章聚类结果"""
    def __init__(self, cluster_id: int, theme: str, articles: List[Article]):
        self.cluster_id = cluster_id
        self.theme = theme  # 聚类主题名称
        self.articles = articles  # 该主题下的文章列表
        self.difficulty_distribution = {}  # 难度分布统计
        
    @property
    def article_count(self) -> int:
        return len(self.articles)
    
    @property
    def avg_importance(self) -> float:
        """平均重要性"""
        if not self.articles:
            return 0
        return sum(getattr(a, 'importance', 5) for a in self.articles) / len(self.articles)
    
    @property
    def primary_difficulty(self) -> str:
        """主要难度级别（该主题下最多的难度标签）"""
        if not self.articles:
            return "进阶"
        difficulties = [getattr(a, 'difficulty', '进阶') for a in self.articles]
        return max(set(difficulties), key=difficulties.count)


class ArticleClustering:
    """
    文章聚类器
    使用 LLM 对文章进行主题聚类
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )
    
    def cluster_articles(self, articles: List[Article], max_clusters: int = 10) -> List[ArticleCluster]:
        """
        对文章进行主题聚类
        
        Args:
            articles: 文章列表（需已有摘要）
            max_clusters: 最大聚类数
            
        Returns:
            聚类结果列表
        """
        if not articles:
            return []
        
        if len(articles) == 1:
            # 只有1篇文章，用 LLM 提炼一个精准主题名
            return self._single_article_theme(articles[0])
        
        # 使用 LLM 进行智能聚类
        return self._llm_clustering(articles, max_clusters)
    
    def _single_article_theme(self, article: Article) -> List[ArticleCluster]:
        """单篇文章时，用 LLM 提炼一个精准的主题名"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的内容编辑。"},
                    {"role": "user", "content": f"""请为以下文章提炼一个简短的主题名（2-6个字），要求准确反映文章核心内容，不要用泛泛的词。

文章标题：{article.title}
核心观点：{article.summary or '无'}

请只输出主题名，不要有任何其他内容。"""},
                ],
                max_tokens=30,
                temperature=0.3,
            )
            theme = response.choices[0].message.content.strip().strip('"\'""''')
            return [ArticleCluster(cluster_id=0, theme=theme, articles=[article])]
        except Exception as e:
            logger.debug(f"单篇主题提炼失败: {e}")
            # 用摘要前15个字作为主题
            theme = (article.summary or article.title)[:15]
            return [ArticleCluster(cluster_id=0, theme=theme, articles=[article])]
    
    def _simple_group_by_category(self, articles: List[Article]) -> List[ArticleCluster]:
        """简单分组：每篇文章用角度小标题或摘要作为主题名，不使用区域名"""
        clusters = []
        for i, article in enumerate(articles):
            # 优先使用角度小标题，其次用摘要前15字，最后用标题前15字
            theme = getattr(article, 'angle_title', '') or ''
            if not theme or theme in (article.category_name, ''):
                theme = (article.summary or article.title)[:15]
            clusters.append(ArticleCluster(
                cluster_id=i,
                theme=theme,
                articles=[article]
            ))
        return clusters
    
    def _llm_clustering(self, articles: List[Article], max_clusters: int) -> List[ArticleCluster]:
        """
        使用 LLM 进行智能主题聚类
        """
        # 构建文章信息
        articles_info = ""
        for i, article in enumerate(articles):
            articles_info += f"{i}. {article.title}\n   摘要：{article.summary or '无'}\n   方向：{article.category_name}\n\n"
        
        prompt = f"""你是一个专业的内容分类专家，需要对以下{len(articles)}篇文章进行主题聚类。

文章列表：
{articles_info}

请将这些文章分成若干主题组，要求：
1. 同一主题的文章讨论的是同一事件、同一话题或高度相关的内容
2. 主题名称要具体精准（2-6个字），如"GPT-5发布"、"央行降准"、"春季招聘"，绝对不能用"AI向"、"财经向"这种区域名
3. 如果某篇文章与其他文章都不相关，单独成组，主题名用该文章的核心话题
4. 宁可多分几个组，也不要把不相关的文章强行凑在一起
5. 最多分成{min(max_clusters, len(articles))}个主题组

请按以下JSON格式输出聚类结果：
{{
  "clusters": [
    {{
      "theme": "主题名称",
      "article_indices": [0, 2, 5]
    }},
    {{
      "theme": "另一个主题",
      "article_indices": [1, 3]
    }}
  ]
}}

注意：
- article_indices 是文章在列表中的序号（从0开始）
- 每篇文章必须且只能属于一个主题组
- 必须输出合法的JSON格式"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的内容分类专家。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=800,
                temperature=0.3,
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 提取 JSON
            import re
            json_match = re.search(r'\{.*?\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                clusters_data = result.get("clusters", [])
                
                # 构建 ArticleCluster 对象
                clusters = []
                for i, cluster_data in enumerate(clusters_data):
                    theme = cluster_data.get("theme", f"主题{i+1}")
                    indices = cluster_data.get("article_indices", [])
                    cluster_articles = [articles[idx] for idx in indices if 0 <= idx < len(articles)]
                    
                    if cluster_articles:
                        clusters.append(ArticleCluster(
                            cluster_id=i,
                            theme=theme,
                            articles=cluster_articles
                        ))
                
                # 检查是否有文章未被聚类
                clustered_indices = set()
                for c in clusters_data:
                    clustered_indices.update(c.get("article_indices", []))
                
                unclustered = [i for i in range(len(articles)) if i not in clustered_indices]
                if unclustered:
                    # 将未聚类的文章单独成组
                    other_articles = [articles[i] for i in unclustered]
                    clusters.append(ArticleCluster(
                        cluster_id=len(clusters),
                        theme="其他资讯",
                        articles=other_articles
                    ))
                
                logger.info(f"LLM 聚类完成：{len(clusters)} 个主题")
                for c in clusters:
                    logger.info(f"  - {c.theme}: {c.article_count} 篇")
                
                return clusters
            
        except Exception as e:
            logger.error(f"LLM 聚类失败: {e}")
        
        # 聚类失败，回退到简单分组
        logger.warning("LLM 聚类失败，使用简单分组")
        return self._simple_group_by_category(articles)
    
    def deduplicate_similar_articles(self, articles: List[Article], 
                                     similarity_threshold: float = 0.8) -> List[Article]:
        """
        去重相似度极高的文章（同一事件的高度重复报道）
        
        Args:
            articles: 文章列表
            similarity_threshold: 相似度阈值（0-1）
            
        Returns:
            去重后的文章列表
        """
        if len(articles) <= 1:
            return articles
        
        # 基于标题和摘要的简单去重
        unique_articles = []
        seen_hashes = set()
        
        for article in articles:
            # 生成内容指纹（标题+摘要的哈希）
            content_key = (article.title + (article.summary or ""))[:100]
            import hashlib
            content_hash = hashlib.md5(content_key.encode()).hexdigest()[:16]
            
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_articles.append(article)
        
        if len(unique_articles) < len(articles):
            logger.info(f"去重：{len(articles)} 篇 -> {len(unique_articles)} 篇")
        
        return unique_articles
