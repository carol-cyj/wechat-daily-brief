"""
内容提炼模块
使用 LLM 对文章进行摘要生成、难度标签分类、重要性评估、术语提取
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

from .config import LLMConfig
from .parser import Article
from .utils import clean_text, truncate_text

logger = logging.getLogger(__name__)

# 核心观点提取 Prompt
SUMMARY_PROMPT = """你是一个专业的内容编辑，擅长从文章中提炼核心观点。
请仔细阅读以下文章正文，提取作者的核心观点和关键信息。

要求：
1. 必须基于文章正文内容提炼，不要泛泛而谈
2. 提取文章真正在讲的核心事件、数据、判断或观点
3. 如果文章讲的是某个具体事件，说明事件本身和影响
4. 如果文章是分析评论，提炼作者的论点和论据
5. 字数80-150字，信息密度要高
6. 不要使用"本文介绍了"、"文章讲述了"这类套话
7. 不要输出通用的风险提示或免责声明

文章标题：{title}
文章来源：{source}
文章正文：
{content}

请直接输出核心观点，不要有任何前缀或解释。"""

# 角度小标题提取 Prompt
ANGLE_TITLE_PROMPT = """你是一个专业的内容编辑，需要为文章提炼一个简短的"角度小标题"。
这个角度小标题用来告诉读者这篇文章的独特视角或切入点，不是文章原标题。

要求：
1. 2-8个字，简洁有力
2. 体现文章的独特角度或核心判断，如"估值逻辑转向"、"裁员与扁平化"、"AI考核引发内卷"
3. 不要用泛泛的词如"行业分析"、"深度解读"、"最新动态"
4. 不要使用文章原标题

文章标题：{title}
核心观点：{summary}

请只输出角度小标题，不要有任何其他内容。"""

# 重要性评估 Prompt
IMPORTANCE_PROMPT = """你是一个资讯编辑，需要评估以下文章在今日资讯中的重要性。
评分标准（1-10分）：
- 10分：重大行业事件、政策变化、头部企业重大发布
- 7-9分：重要行业动态、产品更新、市场趋势
- 4-6分：一般资讯、分析文章、经验分享
- 1-3分：软文、重复信息、低价值内容

文章标题：{title}
文章来源：{source}
文章摘要：{summary}
内容方向：{category}

请只输出一个数字评分（1-10），不要有任何其他内容。"""

# 阅读难度标签 Prompt
DIFFICULTY_PROMPT = """你是一个内容分级专家，需要判断以下文章的阅读难度级别。

分级标准：
- 入门：适合通勤闲聊收听，内容轻松易懂，不需要背景知识，主要是资讯传递或简单观点
- 进阶：需要一定行业认知，涉及专业术语或数据分析，值得停下来思考
- 深度：行业硬核内容，技术细节、深度分析、需要相关背景才能理解

文章标题：{title}
文章摘要：{summary}
内容方向：{category}

请只输出一个标签：入门 或 进阶 或 深度。不要有任何其他内容。"""

# 术语提取 Prompt
TERMS_PROMPT = """你是一个知识管理专家，需要从文章中提取对普通读者可能陌生的专业术语或概念。

文章标题：{title}
文章正文前2000字：
{content}

请提取文章中出现的专业术语、行业黑话、新技术概念、缩写等，按以下JSON格式输出：
[
  {"term": "术语1", "explanation": "一句话解释，让外行也能听懂"},
  {"term": "术语2", "explanation": "一句话解释"}
]

注意：
1. 只提取真正需要解释的概念，常识性词汇不需要
2. 解释要通俗易懂，避免用更复杂的术语来解释
3. 如果没有需要解释的术语，输出空数组 []
4. 必须输出合法的JSON格式"""

# 趋势点评 Prompt
TREND_PROMPT = """你是一个专业的资讯分析师，请根据以下今日各方向核心资讯，生成2-3句「今日趋势点评」。
要求：
1. 对当日四大方向（AI、财经、求职、当地生活）核心信息做整体提炼
2. 指出值得关注的趋势或关联
3. 语言自然流畅，适合语音播报，总字数不超过100字
4. 不要使用"首先、其次、最后"等机械过渡词

今日核心资讯：
{articles}

请直接输出趋势点评文本，不要有任何前缀或解释。"""


class ContentSummarizer:
    """
    内容提炼器
    使用 LLM 生成摘要、难度标签、重要性评分、术语提取
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    def generate_summary(self, article: Article) -> str:
        """为单篇文章提取核心观点"""
        if not article.content:
            logger.warning(f"文章无正文内容，跳过摘要生成: {article.title}")
            return ""

        content = truncate_text(article.content, max_length=4000)

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的内容编辑，擅长提炼文章核心观点。"},
                    {"role": "user", "content": SUMMARY_PROMPT.format(
                        title=article.title,
                        source=article.source,
                        content=content,
                    )},
                ],
                max_tokens=400,
                temperature=self.config.temperature,
            )
            summary = response.choices[0].message.content.strip()
            summary = summary.strip('"\'""''')
            return summary

        except Exception as e:
            logger.error(f"生成摘要失败 [{article.title}]: {e}")
            return ""

    def generate_angle_title(self, article: Article) -> str:
        """为文章提炼角度小标题"""
        summary = article.summary or article.title
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的内容编辑。"},
                    {"role": "user", "content": ANGLE_TITLE_PROMPT.format(
                        title=article.title,
                        summary=summary,
                    )},
                ],
                max_tokens=30,
                temperature=0.3,
            )
            angle = response.choices[0].message.content.strip().strip('"\'""''')
            return angle
        except Exception as e:
            logger.debug(f"生成角度小标题失败 [{article.title}]: {e}")
            return ""

    def evaluate_importance(self, article: Article) -> int:
        """评估文章重要性（1-10分）"""
        summary = article.summary or article.title

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个资讯编辑，负责评估新闻重要性。"},
                    {"role": "user", "content": IMPORTANCE_PROMPT.format(
                        title=article.title,
                        source=article.source,
                        summary=summary,
                        category=article.category_name,
                    )},
                ],
                max_tokens=10,
                temperature=0.1,
            )
            score_text = response.choices[0].message.content.strip()
            match = re.search(r'(\d+)', score_text)
            if match:
                score = int(match.group(1))
                return max(1, min(10, score))
            return 5

        except Exception as e:
            logger.error(f"评估重要性失败 [{article.title}]: {e}")
            return 5

    def evaluate_difficulty(self, article: Article) -> str:
        """评估文章阅读难度（入门/进阶/深度）"""
        summary = article.summary or article.title

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个内容分级专家。"},
                    {"role": "user", "content": DIFFICULTY_PROMPT.format(
                        title=article.title,
                        summary=summary,
                        category=article.category_name,
                    )},
                ],
                max_tokens=10,
                temperature=0.1,
            )
            difficulty = response.choices[0].message.content.strip()
            # 标准化输出
            if "入门" in difficulty:
                return "入门"
            elif "深度" in difficulty:
                return "深度"
            else:
                return "进阶"

        except Exception as e:
            logger.error(f"评估难度失败 [{article.title}]: {e}")
            return "进阶"

    def extract_terms(self, article: Article) -> List[Dict[str, str]]:
        """提取文章中的专业术语及解释"""
        if not article.content:
            return []

        content = truncate_text(article.content, max_length=2000)

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个知识管理专家，擅长提取和解释专业术语。"},
                    {"role": "user", "content": TERMS_PROMPT.format(
                        title=article.title,
                        content=content,
                    )},
                ],
                max_tokens=500,
                temperature=0.2,
            )
            terms_text = response.choices[0].message.content.strip()
            
            # 提取 JSON 部分
            json_match = re.search(r'\[.*?\]', terms_text, re.DOTALL)
            if json_match:
                terms = json.loads(json_match.group())
                if isinstance(terms, list):
                    return terms[:5]  # 最多返回5个术语
            return []

        except Exception as e:
            logger.debug(f"提取术语失败 [{article.title}]: {e}")
            return []

    def generate_trend_comment(self, articles: List[Article]) -> str:
        """生成今日趋势点评"""
        if not articles:
            return "今日暂无足够资讯生成趋势点评。"

        articles_text = ""
        for i, article in enumerate(articles, 1):
            summary = article.summary or article.title
            articles_text += f"{i}. [{article.category_name}] {article.title} - {summary}\n"

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的资讯分析师。"},
                    {"role": "user", "content": TREND_PROMPT.format(articles=articles_text)},
                ],
                max_tokens=300,
                temperature=self.config.temperature,
            )
            comment = response.choices[0].message.content.strip()
            return clean_text(comment)

        except Exception as e:
            logger.error(f"生成趋势点评失败: {e}")
            return "今日资讯已整理完毕，感谢收听。"

    def batch_summarize(self, articles: List[Article]) -> List[Article]:
        """批量为文章生成摘要、角度小标题、难度标签、重要性评分、术语提取"""
        for i, article in enumerate(articles):
            logger.info(f"正在提炼第 {i + 1}/{len(articles)} 篇: {article.title[:30]}...")

            # 生成核心观点
            article.summary = self.generate_summary(article)

            # 生成角度小标题
            article.angle_title = self.generate_angle_title(article)

            # 评估重要性
            article.importance = self.evaluate_importance(article)

            # 评估阅读难度
            article.difficulty = self.evaluate_difficulty(article)

            # 提取术语
            article.terms = self.extract_terms(article)

            logger.info(f"  角度: {article.angle_title}")
            logger.info(f"  摘要: {article.summary[:40]}...")
            logger.info(f"  难度: {article.difficulty} | 重要性: {article.importance}/10")
            if article.terms:
                logger.info(f"  术语: {', '.join([t['term'] for t in article.terms])}")

        return articles

    def analyze_cluster_differences(self, articles: List[Article]) -> str:
        """
        分析同一主题下多篇文章的差异化观点
        
        Args:
            articles: 同一聚类的文章列表（2篇及以上）
            
        Returns:
            差异化观点分析文本
        """
        if len(articles) < 2:
            return ""
        
        # 构建文章信息
        articles_info = ""
        for i, article in enumerate(articles, 1):
            articles_info += f"\n文章{i}：{article.title}\n来源：{article.source}\n摘要：{article.summary or '无'}\n"

        prompt = f"""你是一个专业的媒体分析师，需要对比分析以下{len(articles)}篇关于同一主题的文章，提取它们的差异化观点。

{articles_info}

请分析：
1. 各篇文章的侧重点有何不同？
2. 有哪些独特的观点或角度是某篇文章独有的？
3. 如果存在观点分歧，分歧点在哪里？

要求：
- 用简洁的 bullet points 呈现
- 突出每篇文章的独特价值
- 总字数控制在150字以内
- 适合语音播报，语言自然流畅"""

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的媒体对比分析师。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
                temperature=0.3,
            )
            analysis = response.choices[0].message.content.strip()
            return clean_text(analysis)

        except Exception as e:
            logger.error(f"分析差异化观点失败: {e}")
            return ""
