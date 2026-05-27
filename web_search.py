"""
DialecticEngine - 联网搜索模块
====================================

搜索查询生成策略：LLM 查询生成（主） + 关键词提取（降级）

核心思路：不是"关键词提取"，而是"查询生成"。
传统关键词提取只能抽出孤立词语，丢失语义关系。
用 LLM 理解用户意图，生成搜索引擎友好的查询字符串，
保留短语、实体、否定词和语义关系。

例如：
  用户问："OpenAI的GPT-5什么时候发布，跟谷歌Gemini比有什么优势？"
  LLM 生成：["OpenAI GPT-5 release date 2026", "GPT-5 vs Gemini comparison 2026"]
  而非简单堆砌：OpenAI  GPT-5  谷歌  Gemini  优势

特性：
- LLM 查询生成：结构化 JSON 输出，支持多查询拆分
- 多轮对话上下文：结合对话历史理解指代和省略
- 搜索类型感知：通用/新闻/学术等不同查询风格
- 查询校验：生成后验证查询合理性
- 降级策略：LLM 不可用时使用关键词提取
- 多查询结果去重合并

支持多种搜索后端：智谱 Web Search / Bing / DuckDuckGo / SearXNG
默认使用智谱搜索（国内稳定、无需翻墙），DuckDuckGo 作为降级备用
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

SEARCH_ENGINE = os.environ.get("SEARCH_ENGINE", "zhipu").lower()

ZHIPU_AUTH_KEY = os.environ.get("ZHIPU_AUTH_KEY", "")
ZHIPU_WEB_SEARCH_URL = "https://open.bigmodel.cn/api/paas/v4/web_search"
ZHIPU_SEARCH_ENGINE = os.environ.get("ZHIPU_SEARCH_ENGINE", "search_pro")

BING_API_KEY = os.environ.get("BING_SEARCH_API_KEY", "")
BING_ENDPOINT = os.environ.get(
    "BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search"
)
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080/search")

SEARCH_TIMEOUT = int(os.environ.get("SEARCH_TIMEOUT", "15"))
SEARCH_MAX_RETRIES = int(os.environ.get("SEARCH_MAX_RETRIES", "2"))

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("SEARCH_QUERY_MODEL", "deepseek-chat")

QUERY_GENERATION_TIMEOUT = int(os.environ.get("QUERY_GENERATION_TIMEOUT", "10"))


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = ""


@dataclass
class SearchResponse:
    query: str
    search_keywords: str = ""
    results: list[SearchResult] = field(default_factory=list)
    summary: str = ""

    def to_context_text(self, max_results: int = 10) -> str:
        if not self.results:
            return ""

        display_query = self.search_keywords or self.query
        lines = [f"【联网搜索结果：{display_query}】"]
        for i, r in enumerate(self.results[:max_results], 1):
            lines.append(f"\n{i}. {r.title}")
            lines.append(f"   来源：{r.url}")
            lines.append(f"   摘要：{r.snippet}")
        lines.append("\n--- 搜索结果结束 ---\n")
        return "\n".join(lines)


_QUERY_GENERATION_SYSTEM_PROMPT = """你是一个专业的搜索查询生成器。你的唯一任务是根据对话历史和用户最新问题，生成最适合搜索引擎的查询字符串。

核心原则：
- 不是提取关键词，而是生成保留语义关系的搜索短语
- 搜索引擎需要的是短语和实体，不是孤立词语堆砌

生成规则：
1. 保留关键实体、专有名词、数字和语义关系，不能拆散短语
2. 去除礼貌用语（请、帮我、我想知道）、代词（它、这个、那个）和无关虚词
3. 必须保留否定词（没有、不含、除了、not、no、without、except），这是硬性要求
4. 如果是时间敏感问题（最新、最近、什么时候、今年、当前），加入年份 {year}
5. 语言选择：
   - 涉及中国公司、中文人名、国内政策等中文特有内容 → 生成中文查询
   - 其他情况 → 默认生成英文查询（搜索引擎英文结果更丰富）
6. 每个查询不超过10个词
7. 如果问题包含多个独立子问题，为每个子问题生成一个独立查询
8. 最多生成3个查询

输出格式（严格遵守）：
返回JSON对象，不要任何其他内容：
{{"queries": ["查询1", "查询2"]}}

示例1：
用户：特斯拉最新款Model 3的续航里程是多少？
{{"queries": ["Tesla Model 3 2026 range mileage"]}}

示例2：
用户：OpenAI的GPT-5什么时候发布，跟谷歌Gemini比有什么优势？
{{"queries": ["OpenAI GPT-5 release date 2026", "GPT-5 vs Gemini comparison 2026"]}}

示例3：
用户：帮我搜索斯丹姆于洪娜总监信息
{{"queries": ["北京斯丹姆 于洪娜 总监", "Stemexpress 于洪娜 director"]}}

示例4：
用户：不含咖啡因的饮料有哪些
{{"queries": ["caffeine-free drinks beverages"]}}

示例5：
用户：上周末湖人队的比赛结果
{{"queries": ["Los Angeles Lakers game result May 24 2026"]}}

示例6：
用户：第二个的开放时间呢
（对话历史：用户问巴黎博物馆，助手回答了卢浮宫、奥赛博物馆等）
{{"queries": ["奥赛博物馆 开放时间 2026"]}}"""


def _validate_query(q: str) -> bool:
    """校验生成的查询是否合理"""
    if not q or len(q) < 2:
        return False
    if len(q) > 120:
        return False
    if q.count(" ") > 15:
        return False
    chinese_chars = sum(1 for c in q if "\u4e00" <= c <= "\u9fff")
    if chinese_chars > 0 and chinese_chars < 2:
        return False
    return True


def _generate_search_queries(
    query: str, history: str = "", search_type: str = "general"
) -> list[str]:
    """使用 LLM 生成搜索查询字符串

    Args:
        query: 用户最新问题
        history: 对话历史摘要（可选）
        search_type: 搜索类型 - general/news/academic

    Returns:
        搜索查询字符串列表
    """
    if not DEEPSEEK_API_KEY:
        logger.info("未配置 DEEPSEEK_API_KEY，跳过 LLM 查询生成")
        return []

    now = datetime.now()
    system_prompt = _QUERY_GENERATION_SYSTEM_PROMPT.format(year=now.year)

    type_hints = {
        "general": "",
        "news": "注意：这是新闻搜索，查询中可加入 latest 或 news，侧重时效性。",
        "academic": "注意：这是学术搜索，查询中使用正式学术表达，可加入 paper、arxiv 等词。",
    }

    user_parts = []
    if history:
        history_text = history[:800] if len(history) > 800 else history
        user_parts.append(f"对话历史：\n{history_text}")
    user_parts.append(f"当前日期：{now.strftime('%Y年%m月%d日')}")
    type_hint = type_hints.get(search_type, "")
    if type_hint:
        user_parts.append(type_hint)
    user_parts.append(f"用户最新问题：{query}")
    user_parts.append("输出：")

    user_prompt = "\n\n".join(user_parts)

    try:
        payload = json.dumps({
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 150,
        }, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=QUERY_GENERATION_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not content:
            return []

        queries = _parse_queries_from_llm_output(content)
        queries = [q for q in queries if _validate_query(q)][:3]

        if not queries:
            logger.warning(f"LLM 输出无法解析为有效查询: {content[:100]}")
            return []

        logger.info(f"LLM 生成搜索查询: {queries}")
        return queries

    except Exception as e:
        logger.warning(f"LLM 查询生成失败: {e}")
        return []


def _parse_queries_from_llm_output(content: str) -> list[str]:
    """从 LLM 输出中解析查询列表，兼容 JSON 和纯文本格式"""
    queries = []

    json_match = re.search(r'\{[^{}]*"queries"\s*:\s*\[([^\]]*)\][^{}]*\}', content, re.DOTALL)
    if json_match:
        try:
            json_str = json_match.group(0)
            parsed = json.loads(json_str)
            if isinstance(parsed.get("queries"), list):
                queries = [str(q).strip().strip('"\'') for q in parsed["queries"]]
                queries = [q for q in queries if q]
                if queries:
                    return queries
        except (json.JSONDecodeError, ValueError):
            pass

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and isinstance(parsed.get("queries"), list):
            queries = [str(q).strip().strip('"\'') for q in parsed["queries"]]
            queries = [q for q in queries if q]
            if queries:
                return queries
        if isinstance(parsed, list):
            queries = [str(q).strip().strip('"\'') for q in parsed]
            queries = [q for q in queries if q]
            if queries:
                return queries
    except (json.JSONDecodeError, ValueError):
        pass

    lines = [line.strip() for line in content.split("\n") if line.strip()]
    queries = [re.sub(r'^[\d]+[.)\-\s]*', '', line).strip().strip('"\'') for line in lines]
    queries = [q for q in queries if q and len(q) >= 2]
    return queries


_STOP_WORDS = frozenset([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "他", "她", "它", "们", "那", "些", "什么", "怎么", "如何", "为",
    "为什么", "吗", "呢", "吧", "啊", "呀", "哦", "嗯", "哈", "哪", "哪个", "哪些",
    "能", "可以", "可", "还", "又", "或", "但", "而", "且", "与", "及", "等",
    "被", "把", "让", "给", "从", "向", "对", "比", "以", "于", "之",
    "这个", "那个", "这些", "那些", "其", "此", "该", "每", "各",
    "做", "做做", "得", "地", "所", "来", "过", "后", "前", "中",
    "里", "外", "下", "内", "间", "时", "年", "月", "日",
    "帮", "帮我", "请", "想", "需要", "应该", "能否", "是否",
    "分析", "思考", "考虑", "比较", "选择", "建议", "推荐",
    "一下", "一些", "一点", "这种", "那种", "什么样",
    "现在", "目前", "当前", "已经", "正在", "之前", "之后",
    "如果", "虽然", "因为", "所以", "但是", "不过", "然而",
    "另外", "此外", "同时", "并且", "还是", "或者",
])

_ENTITY_PATTERNS = [
    (r'[\u4e00-\u9fff]{2,4}(?:公司|集团|科技|有限|股份|研究院|实验室|中心|部门|团队|项目)', 'org'),
    (r'[\u4e00-\u9fff]{2,4}(?:总监|经理|主管|负责人|工程师|架构师|专家|科学家)', 'role'),
    (r'(?:AI|LLM|RAG|Agent|NLP|CV|AIGC|SFT|RLHF|PyTorch|TensorFlow|LangChain|DeepSeek|GPT|BERT|Transformer)', 'tech'),
    (r'(?:北京|上海|深圳|广州|杭州|成都|南京|武汉|西安|天津)[市区]?', 'location'),
    (r'\d{4,5}[kK万]?', 'salary'),
    (r'(?:五险一金|公积金|社保|期权|股票|餐补|交通补助|加班)', 'benefit'),
    (r'(?:试用期|转正|入职|离职|合同|外包|正式)', 'employment'),
    (r'(?:在职研究生|考研|硕士|博士|MBA|学历)', 'education'),
    (r'[\u4e00-\u9fff]{2,4}(?:搜索|大模型|算法|开发|测试|运维|产品|设计)', 'field'),
]


def _extract_search_keywords(query: str) -> str:
    """从用户长 query 中提取搜索关键词（降级方案）

    策略：
    1. 提取命名实体（公司名、人名、技术术语、地点等）
    2. 提取英文术语
    3. 对中文部分按标点分句，提取每句中非停用词的2-4字组合
    4. 如果 query 本身较短（<30字），直接返回
    """
    query = query.strip()

    if len(query) <= 30:
        return query

    keywords = []
    seen = set()

    for pattern, etype in _ENTITY_PATTERNS:
        for m in re.findall(pattern, query):
            if m not in seen:
                keywords.append(m)
                seen.add(m)

    for t in re.findall(r'[a-zA-Z][a-zA-Z0-9._-]*', query):
        if len(t) >= 2 and t.lower() not in seen:
            keywords.append(t)
            seen.add(t.lower())

    segments = re.split(r'[，。！？；\n,;!?：:（）()【】\[\]""''—…]+', query)
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        for m in re.findall(r'[\u4e00-\u9fff]{2,4}', seg):
            if m not in _STOP_WORDS and m not in seen and len(m) >= 2:
                keywords.append(m)
                seen.add(m)

    if not keywords:
        return query[:50]

    keyword_str = " ".join(keywords[:15])

    if len(keyword_str) > 80:
        keyword_str = " ".join(keywords[:10])

    return keyword_str


def _should_search(query: str) -> bool:
    """判断用户问题是否需要联网搜索"""
    need_search_keywords = [
        "最新", "最新消息", "最近", "今天", "昨天", "今年", "2024", "2025", "2026",
        "新闻", "热点", "时事", "当前", "现在", "目前", "近期",
        "股价", "股票", "汇率", "天气", "疫情",
        "谁", "哪位", "什么时候", "什么时候出",
        "多少", "几号", "几点",
        "怎么样了", "进展", "动态",
        "搜索", "查找", "查一下", "帮我查", "搜一下",
        "信息", "背景", "简介", "介绍",
        "评价", "口碑", "怎么样", "如何",
        "公司", "企业", "机构", "组织",
        "offer", "面试", "招聘", "薪资", "工资",
    ]

    philosophical_keywords = [
        "应该", "该不该", "要不要", "如何看", "怎么选",
        "人生", "意义", "价值", "道德", "善恶",
        "哲学", "思考", "智慧", "处世",
    ]

    query_lower = query.lower()

    need_score = sum(1 for kw in need_search_keywords if kw in query_lower)
    phil_score = sum(1 for kw in philosophical_keywords if kw in query_lower)

    if need_score >= 2:
        return True
    if need_score >= 1 and phil_score == 0:
        return True

    if len(query) > 100:
        return True

    for pattern, _ in _ENTITY_PATTERNS:
        if re.search(pattern, query):
            return True

    return False


def _execute_search(search_query: str, max_results: int = 10) -> SearchResponse:
    """执行单次搜索，按引擎优先级尝试"""
    if SEARCH_ENGINE == "zhipu" and ZHIPU_AUTH_KEY:
        resp = _search_with_retry(_search_zhipu, search_query, max_results)
        if resp.results:
            return resp
        logger.info("智谱搜索无结果，降级到 DuckDuckGo")
        return _search_with_retry(_search_duckduckgo, search_query, max_results)

    if SEARCH_ENGINE == "bing" and BING_API_KEY:
        resp = _search_with_retry(_search_bing, search_query, max_results)
        if resp.results:
            return resp
        logger.info("Bing 搜索无结果，降级到 DuckDuckGo")
        return _search_with_retry(_search_duckduckgo, search_query, max_results)

    if SEARCH_ENGINE == "searxng":
        resp = _search_with_retry(_search_searxng, search_query, max_results)
        if resp.results:
            return resp
        logger.info("SearXNG 搜索无结果，降级到 DuckDuckGo")
        return _search_with_retry(_search_duckduckgo, search_query, max_results)

    return _search_with_retry(_search_duckduckgo, search_query, max_results)


def web_search(
    query: str, max_results: int = 10, history: str = "", search_type: str = "general"
) -> SearchResponse:
    """
    执行联网搜索

    查询生成策略：
    1. 优先使用 LLM 生成搜索查询（理解语义、保留意图、支持多查询）
    2. LLM 不可用时降级到关键词提取
    3. 多查询结果去重合并

    Args:
        query: 用户原始问题
        max_results: 最多返回结果数
        history: 对话历史摘要（用于多轮对话上下文理解）
        search_type: 搜索类型 - general/news/academic

    Returns:
        SearchResponse
    """
    if not _should_search(query):
        logger.info(f"问题不需要联网搜索: {query[:50]}")
        return SearchResponse(query=query)

    search_queries = _generate_search_queries(query, history, search_type)

    if not search_queries:
        search_queries = [_extract_search_keywords(query)]
        logger.info(f"降级到关键词提取: {search_queries[0][:80]}")

    all_results = []
    seen_urls = set()

    per_query_limit = max(max_results // len(search_queries), 5)

    for sq in search_queries:
        resp = _execute_search(sq, per_query_limit)
        for r in resp.results:
            url_key = r.url.rstrip("/")
            if url_key not in seen_urls:
                seen_urls.add(url_key)
                all_results.append(r)

    all_results = all_results[:max_results]

    search_keywords = " | ".join(search_queries)

    return SearchResponse(
        query=query,
        search_keywords=search_keywords,
        results=all_results,
    )


def _search_with_retry(search_fn, query: str, max_results: int) -> SearchResponse:
    """带重试的搜索执行"""
    last_error = None
    for attempt in range(1, SEARCH_MAX_RETRIES + 1):
        try:
            resp = search_fn(query, max_results)
            if resp.results:
                return resp
            if attempt < SEARCH_MAX_RETRIES:
                logger.info(f"{search_fn.__name__} 无结果，第 {attempt} 次重试...")
                time.sleep(1)
        except Exception as e:
            last_error = e
            logger.warning(f"{search_fn.__name__} 第 {attempt} 次失败: {e}")
            if attempt < SEARCH_MAX_RETRIES:
                time.sleep(2)
    if last_error:
        logger.warning(f"{search_fn.__name__} 全部重试失败: {last_error}")
    return SearchResponse(query=query)


def _search_zhipu(query: str, max_results: int = 10) -> SearchResponse:
    """使用智谱 Web Search API 进行搜索"""
    results = []
    try:
        payload = json.dumps({
            "search_query": query,
            "search_engine": ZHIPU_SEARCH_ENGINE,
            "search_intent": False,
            "count": max(max_results, 10),
        }, ensure_ascii=False).encode("utf-8")

        auth_header = ZHIPU_AUTH_KEY
        if not auth_header.startswith("Bearer "):
            auth_header = "Bearer " + auth_header

        req = urllib.request.Request(
            ZHIPU_WEB_SEARCH_URL,
            data=payload,
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        for result in data.get("search_result", [])[:max_results]:
            title = result.get("title", "")
            link = result.get("link", "")
            content = result.get("content", "")
            media = result.get("media", "")
            refer = result.get("refer", "")
            publish_date = result.get("publish_date", "")

            snippet = content
            if media:
                snippet = f"[{media}] {snippet}"
            if publish_date:
                snippet = f"{publish_date} {snippet}"

            results.append(
                SearchResult(
                    title=title,
                    url=link,
                    snippet=snippet,
                    source="智谱搜索",
                )
            )

    except Exception as e:
        logger.warning(f"智谱搜索失败: {e}")

    return SearchResponse(query=query, results=results)


def _search_duckduckgo(query: str, max_results: int = 10) -> SearchResponse:
    """使用 DuckDuckGo HTML 版本进行搜索（无需 API Key）"""
    results = []
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        result_blocks = re.findall(
            r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        )

        for href, title, snippet in result_blocks[:max_results]:
            title = re.sub(r"<[^>]+>", "", title).strip()
            snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            href = urllib.parse.unquote(href)
            if href.startswith("//"):
                href = "https:" + href
            if title and snippet:
                results.append(
                    SearchResult(title=title, url=href, snippet=snippet, source="DuckDuckGo")
                )

    except Exception as e:
        logger.warning(f"DuckDuckGo 搜索失败: {e}")

    return SearchResponse(query=query, results=results)


def _search_bing(query: str, max_results: int = 10) -> SearchResponse:
    """使用 Bing Web Search API"""
    results = []
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"{BING_ENDPOINT}?q={encoded_query}&count={max_results}&mkt=zh-CN"

        req = urllib.request.Request(
            url,
            headers={"Ocp-Apim-Subscription-Key": BING_API_KEY},
        )

        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        for item in data.get("webPages", {}).get("value", []):
            results.append(
                SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source="Bing",
                )
            )

    except Exception as e:
        logger.warning(f"Bing 搜索失败: {e}")

    return SearchResponse(query=query, results=results)


def _search_searxng(query: str, max_results: int = 10) -> SearchResponse:
    """使用 SearXNG 自建搜索实例"""
    results = []
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"{SEARXNG_URL}?q={encoded_query}&format=json&language=zh-CN"

        req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        for item in data.get("results", [])[:max_results]:
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source="SearXNG",
                )
            )

    except Exception as e:
        logger.warning(f"SearXNG 搜索失败: {e}")

    return SearchResponse(query=query, results=results)
