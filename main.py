#!/usr/bin/env python3
"""
公众号内容聚合与有声化工具 - 主程序入口 v4.1

结构：
- 按区域分组（AI向、财经向、求职向、生活向）
- 每个区域内按主题聚类
- 每个主题下显示各文章的观点（摘要），附公众号名称和链接
- 关键词高亮、评论区高赞、阅读时长、热度标记
"""

import sys
import os
import time
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import click

sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_config, get_output_paths, AppConfig
from src.fetcher import ArticleFetcher
from src.summarizer import ContentSummarizer
from src.aggregator import BriefAggregator
from src.clustering import ArticleClustering, ArticleCluster
from src.tts import TTSEngine, build_brief_script
from src.utils import setup_logging, get_today_str, format_duration

logger = logging.getLogger(__name__)


def highlight_keywords(text, all_terms):
    """在文本中高亮术语关键词，用 <b> 标签加粗"""
    if not all_terms or not text:
        return text
    # 按术语长度降序排列，优先匹配长术语
    sorted_terms = sorted(all_terms.keys(), key=len, reverse=True)
    for term in sorted_terms:
        # 避免重复替换
        escaped = re.escape(term)
        text = re.sub(
            escaped,
            f'<b class="kw">{term}</b>',
            text,
            flags=re.IGNORECASE
        )
    return text


def cluster_articles_by_category(articles, llm_config):
    """
    先按区域分组，再在每个区域内按主题聚类
    
    Returns:
        dict: {category_name: [ArticleCluster, ...], ...}
    """
    # 按区域分组
    articles_by_category = defaultdict(list)
    for article in articles:
        articles_by_category[article.category_name].append(article)
    
    # 每个区域内进行主题聚类
    clustering = ArticleClustering(llm_config)
    result = {}
    
    for category_name, cat_articles in articles_by_category.items():
        if len(cat_articles) == 0:
            continue
        try:
            clusters = clustering.cluster_articles(cat_articles, max_clusters=5)
            result[category_name] = clusters
        except Exception as e:
            logger.warning(f"聚类失败 [{category_name}]: {e}")
            # 失败时每篇文章单独一个主题
            result[category_name] = [
                ArticleCluster(
                    cluster_id=i, 
                    theme=art.summary[:30] if art.summary else art.title[:30],
                    articles=[art]
                )
                for i, art in enumerate(cat_articles)
            ]
    
    return result


def generate_html_brief(category_clusters, date_str, trend_comment, output_path, all_terms, audio_path=""):
    """
    生成 HTML 简报页面
    
    结构：区域 → 主题 → 观点（角度标题 + 摘要 + 关键词高亮 + 公众号 + 链接 + 评论）
    优化：关键词加粗、热度标记、阅读时长、评论区高赞、回到顶部、生成时间、语音播报
    """
    
    # 统计
    total_articles = sum(
        len(cluster.articles) 
        for clusters in category_clusters.values() 
        for cluster in clusters
    )
    total_themes = sum(len(clusters) for clusters in category_clusters.values())
    total_comments = sum(
        len(getattr(art, 'top_comments', []))
        for clusters in category_clusters.values()
        for cluster in clusters
        for art in cluster.articles
    )
    gen_time = datetime.now().strftime("%H:%M")
    
    # 区域顺序和配色
    category_order = ["AI向", "财经向", "求职向", "生活向"]
    category_icons = {
        "AI向": "🤖",
        "财经向": "💰", 
        "求职向": "💼",
        "生活向": "🏠"
    }
    category_colors = {
        "AI向": ("#6366f1", "#8b5cf6"),
        "财经向": ("#f59e0b", "#ef4444"),
        "求职向": ("#10b981", "#06b6d4"),
        "生活向": ("#ec4899", "#f97316"),
    }
    
    # 构建区域 HTML
    categories_html = ""
    
    for category_name in category_order:
        if category_name not in category_clusters:
            continue
            
        clusters = category_clusters[category_name]
        icon = category_icons.get(category_name, "📰")
        c1, c2 = category_colors.get(category_name, ("#ff6b35", "#00d4aa"))
        
        # 该区域的主题列表
        themes_html = ""
        for i, cluster in enumerate(clusters, 1):
            theme = cluster.theme
            
            # 该主题下的观点列表
            views_html = ""
            for article in cluster.articles:
                summary = article.summary or "（暂无摘要）"
                source = article.source
                url = article.url
                angle_title = getattr(article, 'angle_title', '')
                
                # 关键词高亮
                summary = highlight_keywords(summary, all_terms)
                
                # 热度标记：基于评论互动数据（评论点赞总量）
                comments = getattr(article, 'top_comments', [])
                total_likes = sum(c.get('likes', 0) for c in comments)
                hot_badge = ""
                if total_likes >= 500:
                    hot_badge = f'<span class="hot-badge">🔥 热点 · {total_likes} 赞</span>'
                elif total_likes >= 100:
                    hot_badge = f'<span class="hot-badge warm">🔥 {total_likes} 赞</span>'
                
                # 评论区高赞
                comments_html = ""
                if comments:
                    comments_list = ""
                    for rank, c in enumerate(comments[:3], 1):
                        author = c.get('author', '匿名')
                        content_text = c.get('content', '')
                        likes = c.get('likes', 0)
                        # 高亮评论中的关键词
                        content_text = highlight_keywords(content_text, all_terms)
                        rank_icon = ["🥇", "🥈", "🥉"][rank - 1] if rank <= 3 else f"{rank}."
                        comments_list += f'''
                        <div class="comment-item">
                            <span class="comment-rank">{rank_icon}</span>
                            <div class="comment-body">
                                <span class="comment-text">{content_text}</span>
                                <div class="comment-footer">
                                    <span class="comment-author">{author}</span>
                                    <span class="comment-likes">👍 {likes}</span>
                                </div>
                            </div>
                        </div>'''
                    comments_html = f'''
                    <div class="comments-section">
                        <div class="comments-toggle" onclick="this.parentElement.classList.toggle('expanded')">
                            <span>💬 评论区高赞 TOP{min(len(comments), 3)}</span>
                            <span class="comments-arrow">▾</span>
                        </div>
                        <div class="comments-list">
                            {comments_list}
                        </div>
                    </div>'''
                
                # 角度小标题
                angle_html = ""
                if angle_title:
                    angle_html = f'<div class="view-angle">▸ {angle_title}</div>'
                
                # 元信息行
                meta_items = f'<span class="view-source">📌 {source}</span>'
                meta_items += f'<a href="{url}" target="_blank" class="view-link">阅读原文 →</a>'
                
                views_html += f'''
                <div class="view-item">
                    <div class="view-top">
                        {angle_html}
                        {hot_badge}
                    </div>
                    <div class="view-content">{summary}</div>
                    <div class="view-meta">
                        {meta_items}
                    </div>
                    {comments_html}
                </div>'''
            
            themes_html += f'''
            <div class="theme-card">
                <div class="theme-title">
                    <span class="theme-num">{i}</span>
                    <span class="theme-name">{theme}</span>
                    <span class="theme-count">{len(cluster.articles)} 篇</span>
                </div>
                <div class="views-container">
                    {views_html}
                </div>
            </div>'''
        
        categories_html += f'''
        <section class="category-section" id="cat-{category_name}">
            <div class="category-header" style="background: linear-gradient(135deg, {c1}22, {c2}22); border-left: 3px solid {c1};">
                <span class="category-icon">{icon}</span>
                <span class="category-name">{category_name}</span>
                <span class="category-count">{len(clusters)} 个主题</span>
            </div>
            <div class="themes-list">
                {themes_html}
            </div>
        </section>'''
    
    # 术语速查
    glossary_html = ""
    if all_terms:
        terms_list = ""
        for term, explanation in sorted(all_terms.items()):
            terms_list += f'''
            <div class="glossary-item">
                <span class="glossary-term">{term}</span>
                <span class="glossary-def">{explanation}</span>
            </div>'''
        glossary_html = f'''
        <section class="glossary-section">
            <div class="section-title">📖 术语速查（{len(all_terms)}个）</div>
            <div class="glossary-list">{terms_list}</div>
        </section>'''
    
    # 趋势点评
    trend_html = f'''
    <section class="trend-section">
        <div class="trend-label">📊 今日趋势点评</div>
        <div class="trend-content">{trend_comment}</div>
    </section>'''
    
    # 语音播报播放器
    audio_html = ""
    if audio_path:
        audio_filename = os.path.basename(audio_path)
        audio_html = f'''
    <section class="audio-section">
        <div class="audio-label">🔊 语音播报</div>
        <div class="audio-player">
            <audio controls preload="metadata">
                <source src="{audio_filename}" type="audio/mpeg">
            </audio>
            <div class="audio-hint">点击播放，通勤路上听简报</div>
        </div>
    </section>'''
    
    # 完整 HTML
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>每日资讯简报 - {date_str}</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0a0a0f;
            --surface: #13131c;
            --surface-2: #1c1c2a;
            --border: rgba(255,255,255,0.08);
            --text: #e8e6e3;
            --text-muted: #8a8898;
            --accent: #ff6b35;
            --accent-2: #00d4aa;
            --kw-color: #fbbf24;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html {{ font-size: 16px; scroll-behavior: smooth; }}
        body {{
            font-family: 'Noto Sans SC', -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            min-height: 100vh;
        }}

        .container {{
            max-width: 680px;
            margin: 0 auto;
            padding: 0 16px 40px;
        }}

        /* Header */
        .header {{
            text-align: center;
            padding: 32px 0 24px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
        }}
        .header-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: var(--surface-2);
            border-radius: 100px;
            padding: 4px 14px;
            font-size: 10px;
            color: var(--text-muted);
            letter-spacing: 2px;
            margin-bottom: 12px;
        }}
        .header-badge .dot {{
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--accent);
        }}
        .header h1 {{
            font-size: 26px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .header .date {{
            font-size: 13px;
            color: var(--text-muted);
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 24px;
            margin-top: 16px;
        }}
        .stat {{ text-align: center; }}
        .stat-value {{
            font-size: 22px;
            font-weight: 700;
            color: var(--accent);
        }}
        .stat-label {{
            font-size: 10px;
            color: var(--text-muted);
        }}

        /* Category Section */
        .category-section {{
            margin-bottom: 32px;
        }}
        .category-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 14px 16px;
            border-radius: 12px;
            margin-bottom: 16px;
            border: 1px solid var(--border);
        }}
        .category-icon {{ font-size: 24px; }}
        .category-name {{
            font-size: 18px;
            font-weight: 700;
            flex: 1;
        }}
        .category-count {{
            font-size: 12px;
            color: var(--text-muted);
        }}

        /* Theme Card */
        .theme-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 12px;
            overflow: hidden;
            transition: border-color 0.2s;
        }}
        .theme-card:hover {{
            border-color: rgba(255,255,255,0.15);
        }}
        .theme-title {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 14px 16px;
            background: var(--surface-2);
            border-bottom: 1px solid var(--border);
        }}
        .theme-num {{
            width: 24px;
            height: 24px;
            border-radius: 6px;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 700;
            flex-shrink: 0;
        }}
        .theme-name {{
            font-size: 15px;
            font-weight: 600;
            line-height: 1.4;
            flex: 1;
        }}
        .theme-count {{
            font-size: 11px;
            color: var(--text-muted);
            white-space: nowrap;
        }}

        /* View Item */
        .view-item {{
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
        }}
        .view-item:last-child {{ border-bottom: none; }}
        .view-top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }}
        .view-angle {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text);
            line-height: 1.4;
        }}
        .hot-badge {{
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 100px;
            background: rgba(255,75,75,0.15);
            color: #ff6b6b;
            white-space: nowrap;
            flex-shrink: 0;
        }}
        .hot-badge.warm {{
            background: rgba(255,180,50,0.12);
            color: #ffb432;
        }}
        .view-content {{
            font-size: 14px;
            color: var(--text-muted);
            line-height: 1.7;
            margin-bottom: 10px;
        }}
        .view-content b.kw {{
            color: var(--kw-color);
            font-weight: 600;
        }}
        .view-meta {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 12px;
            font-size: 12px;
        }}
        .view-source {{ color: var(--accent-2); }}
        .view-time {{ color: var(--text-muted); }}
        .view-link {{
            color: var(--accent);
            text-decoration: none;
            margin-left: auto;
        }}
        .view-link:hover {{ text-decoration: underline; }}

        /* Comments */
        .comments-section {{
            margin-top: 10px;
            border-top: 1px dashed var(--border);
            padding-top: 8px;
        }}
        .comments-toggle {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 0;
            cursor: pointer;
            font-size: 12px;
            color: var(--text-muted);
            user-select: none;
        }}
        .comments-toggle:hover {{ color: var(--text); }}
        .comments-arrow {{
            transition: transform 0.2s;
            font-size: 10px;
        }}
        .comments-section.expanded .comments-arrow {{
            transform: rotate(180deg);
        }}
        .comments-list {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }}
        .comments-section.expanded .comments-list {{
            max-height: 500px;
        }}
        .comment-item {{
            display: flex;
            align-items: flex-start;
            gap: 8px;
            font-size: 12px;
            margin-bottom: 6px;
            padding: 8px 10px;
            background: var(--surface-2);
            border-radius: 8px;
        }}
        .comment-rank {{
            font-size: 14px;
            flex-shrink: 0;
            line-height: 1.4;
        }}
        .comment-body {{
            flex: 1;
            min-width: 0;
        }}
        .comment-text {{
            color: var(--text-muted);
            line-height: 1.5;
            word-break: break-word;
        }}
        .comment-text b.kw {{
            color: var(--kw-color);
            font-weight: 600;
        }}
        .comment-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 4px;
        }}
        .comment-author {{
            color: var(--accent-2);
            font-size: 11px;
        }}
        .comment-likes {{
            color: var(--text-muted);
            font-size: 11px;
        }}

        /* Glossary */
        .glossary-section {{
            background: var(--surface);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
        }}
        .glossary-section .section-title {{
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 12px;
        }}
        .glossary-item {{
            display: flex;
            gap: 10px;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
        }}
        .glossary-item:last-child {{ border-bottom: none; }}
        .glossary-term {{
            font-weight: 700;
            color: var(--kw-color);
            min-width: 80px;
            flex-shrink: 0;
        }}
        .glossary-def {{ color: var(--text-muted); }}

        /* Trend */
        .trend-section {{
            background: linear-gradient(135deg, var(--surface), var(--surface-2));
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
        }}
        .trend-label {{
            font-size: 11px;
            font-weight: 700;
            color: var(--accent);
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        .trend-content {{
            font-size: 14px;
            line-height: 1.8;
            color: var(--text-muted);
        }}

        /* Back to top */
        .back-top {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: var(--surface-2);
            border: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            opacity: 0;
            transition: opacity 0.3s, transform 0.3s;
            transform: translateY(10px);
            z-index: 100;
        }}
        .back-top.visible {{
            opacity: 1;
            transform: translateY(0);
        }}
        .back-top:hover {{
            background: var(--accent);
            color: #fff;
        }}

        /* Audio Player */
        .audio-section {{
            background: linear-gradient(135deg, var(--surface), var(--surface-2));
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
        }}
        .audio-label {{
            font-size: 11px;
            font-weight: 700;
            color: var(--accent-2);
            letter-spacing: 1px;
            margin-bottom: 12px;
        }}
        .audio-player audio {{
            width: 100%;
            height: 40px;
            border-radius: 8px;
            outline: none;
        }}
        .audio-hint {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 8px;
            text-align: center;
        }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 20px 0;
            border-top: 1px solid var(--border);
            font-size: 11px;
            color: var(--text-muted);
        }}
        .footer .gen-time {{
            margin-top: 4px;
            font-size: 10px;
        }}

        @media (min-width: 640px) {{
            .container {{ padding: 0 24px 60px; }}
            .header h1 {{ font-size: 28px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="header-badge"><span class="dot"></span>Daily Brief</div>
            <h1>每日资讯简报</h1>
            <div class="date">{date_str}</div>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{len(category_clusters)}</div>
                    <div class="stat-label">区域</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{total_themes}</div>
                    <div class="stat-label">主题</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{total_articles}</div>
                    <div class="stat-label">观点</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{total_comments}</div>
                    <div class="stat-label">评论</div>
                </div>
            </div>
        </header>

        {categories_html}

        {glossary_html}

        {trend_html}

        {audio_html}

        <footer class="footer">
            由「公众号内容聚合与有声化工具」自动生成 · v4.1
            <div class="gen-time">生成时间：{gen_time}</div>
        </footer>
    </div>

    <div class="back-top" onclick="window.scrollTo({{top:0}})" id="backTop">↑</div>

    <script>
        window.addEventListener('scroll', function() {{
            var btn = document.getElementById('backTop');
            if (window.scrollY > 400) {{
                btn.classList.add('visible');
            }} else {{
                btn.classList.remove('visible');
            }}
        }});
    </script>
</body>
</html>'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    logger.info(f"HTML 简报已保存: {output_path}")
    return output_path


def run_pipeline(config: AppConfig, date_str: str, text_only: bool = False) -> dict:
    """执行完整的简报生成流水线"""
    start_time = time.time()
    stats = {
        "date": date_str,
        "articles_fetched": 0,
        "articles_parsed": 0,
        "text_output": "",
        "html_output": "",
        "audio_output": "",
        "success": False,
        "error": "",
    }

    # Step 1: 抓取文章
    logger.info("=" * 60)
    logger.info("Step 1: 抓取公众号文章...")
    logger.info("=" * 60)

    try:
        fetcher = ArticleFetcher(
            config.fetcher,
            wewe_base_url=config.wewe_base_url,
            wewe_auth_code=config.wewe_auth_code,
        )
        articles = fetcher.fetch_all(config.categories)
        stats["articles_fetched"] = len(articles)

        if not articles:
            stats["error"] = "未抓取到任何文章"
            return stats

    except Exception as e:
        stats["error"] = str(e)
        return stats

    # Step 2: 解析正文
    logger.info("=" * 60)
    logger.info("Step 2: 解析文章正文...")
    logger.info("=" * 60)

    parsed_articles = []
    for i, article in enumerate(articles):
        logger.info(f"解析第 {i + 1}/{len(articles)} 篇: {article.title[:30]}...")
        article = fetcher.fetch_article_content(article)
        content_len = len(article.content) if article.content else 0
        logger.info(f"  内容长度: {content_len} 字符")
        
        if article.content and content_len > 100:
            parsed_articles.append(article)

    stats["articles_parsed"] = len(parsed_articles)

    if not parsed_articles:
        stats["error"] = "未能获取文章正文"
        return stats

    # Step 3: AI 分析
    logger.info("=" * 60)
    logger.info("Step 3: AI 智能分析...")
    logger.info("=" * 60)

    try:
        summarizer = ContentSummarizer(config.llm)
        parsed_articles = summarizer.batch_summarize(parsed_articles)
    except Exception as e:
        logger.error(f"AI 分析失败: {e}")
        stats["error"] = f"AI 分析失败: {e}"
        return stats

    # Step 4: 按区域分组并聚类
    logger.info("=" * 60)
    logger.info("Step 4: 按区域分组并聚类...")
    logger.info("=" * 60)

    try:
        category_clusters = cluster_articles_by_category(parsed_articles, config.llm)
        
        # 统计
        for cat_name, clusters in category_clusters.items():
            logger.info(f"  [{cat_name}] {len(clusters)} 个主题")
            
    except Exception as e:
        logger.error(f"聚类失败: {e}")
        stats["error"] = str(e)
        return stats

    # Step 5: 生成简报
    logger.info("=" * 60)
    logger.info("Step 5: 生成简报...")
    logger.info("=" * 60)

    try:
        # 收集所有文章用于趋势点评
        all_articles = []
        for clusters in category_clusters.values():
            for cluster in clusters:
                all_articles.extend(cluster.articles)

        # 收集术语
        all_terms = {}
        for article in all_articles:
            terms = getattr(article, 'terms', [])
            for term_info in terms:
                term = term_info.get('term', '')
                explanation = term_info.get('explanation', '')
                if term and explanation:
                    all_terms[term] = explanation

        # 趋势点评
        trend_comment = summarizer.generate_trend_comment(all_articles)

        # 保存路径
        text_path, audio_path = get_output_paths(config, date_str)
        Path(text_path).parent.mkdir(parents=True, exist_ok=True)

        # 保存 Markdown（简化版）
        md_content = f"# 每日资讯简报 - {date_str}\n\n"
        for cat_name, clusters in category_clusters.items():
            md_content += f"## {cat_name}\n\n"
            for cluster in clusters:
                md_content += f"### {cluster.theme}\n\n"
                for article in cluster.articles:
                    md_content += f"- {article.summary} 📌 [{article.source}]({article.url})\n"
                md_content += "\n"
        
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        stats["text_output"] = text_path

        # 保存 HTML
        html_path = text_path.replace('.md', '.html')
        generate_html_brief(category_clusters, date_str, trend_comment, html_path, all_terms, audio_path)
        stats["html_output"] = html_path

    except Exception as e:
        stats["error"] = str(e)
        return stats

    # Step 6: 语音合成
    if not text_only:
        logger.info("=" * 60)
        logger.info("Step 6: 语音合成...")
        logger.info("=" * 60)

        try:
            tts = TTSEngine(config.tts)
            script = build_brief_script(all_articles, trend_comment, date_str)
            success = tts.synthesize(script, audio_path)
            if success:
                stats["audio_output"] = audio_path
        except Exception as e:
            logger.error(f"语音合成失败: {e}")

    elapsed = time.time() - start_time
    stats["success"] = True

    logger.info("=" * 60)
    logger.info("✅ 简报生成完成！")
    logger.info(f"  HTML: {stats['html_output']}")
    logger.info(f"  耗时: {format_duration(elapsed)}")
    logger.info("=" * 60)

    return stats


@click.command()
@click.option("--config", "-c", "config_path", default="config.yaml", help="配置文件路径")
@click.option("--date", "-d", "target_date", default=None, help="指定日期")
@click.option("--text-only", is_flag=True, help="仅生成文字简报")
@click.option("--verbose", "-v", is_flag=True, help="详细日志")
def main(config_path: str, target_date: str, text_only: bool, verbose: bool):
    """📰 公众号内容聚合与有声化工具 v4.0"""
    
    setup_logging(logging.DEBUG if verbose else logging.INFO)
    date_str = target_date or get_today_str()

    click.echo(f"📰 公众号内容聚合与有声化工具 v4.0")
    click.echo(f"📅 日期: {date_str}")

    try:
        config = load_config(config_path)
    except Exception as e:
        click.echo(f"❌ 配置加载失败: {e}")
        sys.exit(1)

    stats = run_pipeline(config, date_str, text_only)

    if stats["success"]:
        click.echo("")
        click.echo("🎉 简报生成成功！")
        if stats.get('html_output'):
            click.echo(f"🌐 HTML: {stats['html_output']}")
        if stats['text_output']:
            click.echo(f"📝 Markdown: {stats['text_output']}")
        if stats['audio_output']:
            click.echo(f"🔊 语音: {stats['audio_output']}")
    else:
        click.echo(f"❌ 失败: {stats['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
