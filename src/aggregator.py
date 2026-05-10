"""
简报聚合模块
负责按方向聚合文章、主题聚类、生成最终简报
支持三级标签、差异化观点、术语注释
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from .config import BriefConfig
from .parser import Article
from .clustering import ArticleCluster
from .utils import clean_text

logger = logging.getLogger(__name__)


class BriefAggregator:
    """
    简报聚合器
    将多方向文章按主题聚类，生成结构化的每日简报
    """

    def __init__(self, config: BriefConfig):
        self.config = config

    def aggregate(self, clusters: List[ArticleCluster],
                  trend_comment: str = "",
                  date_str: str = "",
                  all_terms: Dict[str, str] = None) -> str:
        """
        生成最终简报文本

        Args:
            clusters: 已聚类的文章主题列表
            trend_comment: 趋势点评
            date_str: 日期字符串
            all_terms: 所有术语的解释字典 {术语: 解释}

        Returns:
            Markdown 格式的简报文本
        """
        if self.config.output_format == "json":
            return self._generate_json(clusters, trend_comment, date_str, all_terms)
        else:
            return self._generate_markdown(clusters, trend_comment, date_str, all_terms)

    def select_top_clusters(self, clusters: List[ArticleCluster]) -> List[ArticleCluster]:
        """
        从所有聚类中选取核心主题
        保证各方向均衡覆盖

        Args:
            clusters: 所有文章聚类

        Returns:
            选取的核心聚类列表
        """
        if not clusters:
            return []

        # 按平均重要性排序
        clusters.sort(key=lambda c: c.avg_importance, reverse=True)

        # 限制总数
        top_n = self.config.top_n
        selected = clusters[:top_n]

        logger.info(f"从 {len(clusters)} 个主题中选取了 {len(selected)} 个核心主题")
        return selected

    def _generate_markdown(self, clusters: List[ArticleCluster],
                           trend_comment: str, date_str: str,
                           all_terms: Dict[str, str] = None) -> str:
        """生成 Markdown 格式简报（按方向分组，内部按主题聚类）"""
        lines = []

        # 标题
        lines.append(f"# 📰 每日资讯简报")
        lines.append(f"**日期**: {date_str}")
        lines.append("")

        # 按方向分组
        direction_clusters = defaultdict(list)
        for cluster in clusters:
            # 获取该主题的主要方向（取第一篇文章的方向）
            if cluster.articles:
                cat_key = cluster.articles[0].category
                direction_clusters[cat_key].append(cluster)

        # 方向标签 emoji
        category_emoji = {
            "ai": "🤖",
            "finance": "💰",
            "career": "💼",
            "local_life": "🏠",
        }

        # 按方向输出
        for cat_key in ["ai", "finance", "career", "local_life"]:
            if cat_key not in direction_clusters:
                continue

            clusters_in_dir = direction_clusters[cat_key]
            emoji = category_emoji.get(cat_key, "📌")
            cat_name = clusters_in_dir[0].articles[0].category_name if clusters_in_dir else cat_key

            lines.append(f"## {emoji} {cat_name}")
            lines.append("")

            # 该方向下的各个主题
            for i, cluster in enumerate(clusters_in_dir, 1):
                theme = cluster.theme
                difficulty = cluster.primary_difficulty
                avg_importance = cluster.avg_importance

                # 难度标签 emoji
                difficulty_emoji = {
                    "入门": "🟢",
                    "进阶": "🟡",
                    "深度": "🔴",
                }.get(difficulty, "⚪")

                lines.append(f"### {i}. {theme} {difficulty_emoji} {difficulty}")
                lines.append("")

                # 如果有多篇文章，显示差异化分析
                if cluster.article_count > 1:
                    lines.append("**📊 多视角解读：**")
                    # 差异化观点在 summarizer 中生成，存储在第一篇文章的 cluster_analysis 中
                    first_article = cluster.articles[0]
                    diff_analysis = getattr(first_article, 'cluster_analysis', '')
                    if diff_analysis:
                        lines.append(diff_analysis)
                    lines.append("")

                # 列出该主题下的文章
                for j, article in enumerate(cluster.articles, 1):
                    summary = article.summary or ""
                    importance = getattr(article, 'importance', 5)
                    importance_bar = "⭐" * min(5, max(1, importance // 2))
                    article_difficulty = getattr(article, 'difficulty', '进阶')

                    lines.append(f"**{j}. {article.title}**")
                    if summary:
                        lines.append(f"> {summary}")
                    lines.append(f"- 📌 来源: {article.source}")
                    lines.append(f"- 🔥 重要度: {importance_bar} ({importance}/10)")
                    lines.append(f"- 📚 难度: {article_difficulty}")

                    # 显示该文章的术语
                    terms = getattr(article, 'terms', [])
                    if terms:
                        term_strs = [f"**{t['term']}**: {t['explanation']}" for t in terms]
                        lines.append(f"- 💡 术语: {'; '.join(term_strs)}")

                    if article.url:
                        lines.append(f"- 🔗 [阅读原文]({article.url})")
                    lines.append("")

        # 术语表（汇总）
        if all_terms:
            lines.append("---")
            lines.append("")
            lines.append("## 📖 术语速查")
            lines.append("")
            for term, explanation in sorted(all_terms.items()):
                lines.append(f"- **{term}**: {explanation}")
            lines.append("")

        # 趋势点评
        if trend_comment:
            lines.append("---")
            lines.append("")
            lines.append("## 📊 今日趋势点评")
            lines.append("")
            lines.append(f"> {trend_comment}")
            lines.append("")

        # 页脚
        lines.append("---")
        lines.append("")
        lines.append("*由「公众号内容聚合与有声化工具」自动生成*")

        return "\n".join(lines)

    def _generate_json(self, clusters: List[ArticleCluster],
                       trend_comment: str, date_str: str,
                       all_terms: Dict[str, str] = None) -> str:
        """生成 JSON 格式简报"""
        import json

        cluster_list = []
        for cluster in clusters:
            articles_data = []
            for article in cluster.articles:
                articles_data.append({
                    "title": article.title,
                    "summary": article.summary or "",
                    "source": article.source,
                    "difficulty": getattr(article, 'difficulty', '进阶'),
                    "importance": getattr(article, 'importance', 5),
                    "terms": getattr(article, 'terms', []),
                    "url": article.url,
                    "publish_date": article.publish_date,
                })

            cluster_list.append({
                "theme": cluster.theme,
                "difficulty": cluster.primary_difficulty,
                "avg_importance": cluster.avg_importance,
                "article_count": cluster.article_count,
                "articles": articles_data,
            })

        result = {
            "date": date_str,
            "total_clusters": len(cluster_list),
            "clusters": cluster_list,
            "terms": all_terms or {},
            "trend_comment": trend_comment,
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
