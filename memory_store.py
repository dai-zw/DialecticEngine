"""
DialecticEngine - 双文件记忆存储系统
存储两份记忆：
  1. 原文记忆 (raw/) - 完整对话记录
  2. 摘要记忆 (summary/) - query + 回复摘要
通过相同的 memory_id 关联
"""

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
MEMORY_DIR = ROOT / "data" / "memory"
RAW_DIR = MEMORY_DIR / "raw"
SUMMARY_DIR = MEMORY_DIR / "summary"

# 确保目录存在
RAW_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)


class MemoryStore:
    """双文件记忆存储管理器"""

    _lock = threading.Lock()

    @staticmethod
    def _generate_id() -> str:
        """生成记忆唯一ID"""
        return f"mem_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _date_path() -> Path:
        """按日期分目录：YYYY-MM/DD/"""
        now = datetime.now(timezone.utc)
        return Path(f"{now:%Y-%m}") / f"{now:%d}"

    @classmethod
    def save(
        cls,
        session_id: str,
        user_query: str,
        selected_skills: list[str],
        execution_mode: str,
        full_response: str,
        turns: list[dict] | None = None,
        synthesis: str = "",
        skill_outputs: list[dict] | None = None,
        confidence: float = 0.0,
        reasoning: str = "",
        metadata: dict | None = None,
    ) -> str:
        """
        保存一次对话的双份记忆

        Args:
            session_id: 会话ID
            user_query: 用户原始问题
            selected_skills: 选中的技能列表
            execution_mode: 执行模式
            full_response: 完整回复文本
            turns: 辩论轮次记录（可选）
            synthesis: 综合结论（可选）
            skill_outputs: 各技能输出（可选）
            confidence: 置信度
            reasoning: 路由推理
            metadata: 额外元数据

        Returns:
            memory_id: 记忆唯一ID
        """
        memory_id = cls._generate_id()
        timestamp = datetime.now(timezone.utc).isoformat()
        date_subdir = cls._date_path()

        # 构建原文记忆
        raw_record = {
            "memory_id": memory_id,
            "session_id": session_id,
            "timestamp": timestamp,
            "user_query": user_query,
            "selected_skills": selected_skills,
            "execution_mode": execution_mode,
            "full_response": full_response,
            "turns": turns or [],
            "synthesis": synthesis,
            "skill_outputs": skill_outputs or [],
            "confidence": confidence,
            "reasoning": reasoning,
            "metadata": metadata or {},
            "version": "1.0",
        }

        # 构建摘要记忆
        query_summary = cls._summarize_text(user_query, max_length=80)
        response_summary = cls._summarize_text(
            synthesis or full_response, max_length=300
        )
        key_points = cls._extract_key_points(synthesis or full_response)
        skill_summaries = cls._summarize_skill_outputs(skill_outputs or [])
        topics = cls._extract_topics(user_query, full_response)

        summary_record = {
            "memory_id": memory_id,
            "session_id": session_id,
            "timestamp": timestamp,
            "query_summary": query_summary,
            "response_summary": response_summary,
            "key_points": key_points,
            "selected_skills": selected_skills,
            "skill_summaries": skill_summaries,
            "conclusion": cls._extract_conclusion(synthesis or full_response),
            "topics": topics,
            "confidence": confidence,
            "execution_mode": execution_mode,
            "version": "1.0",
        }

        # 写入文件
        with cls._lock:
            raw_path = RAW_DIR / date_subdir / f"raw_{memory_id}.json"
            summary_path = SUMMARY_DIR / date_subdir / f"summary_{memory_id}.json"

            raw_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                with open(raw_path, "w", encoding="utf-8") as f:
                    json.dump(raw_record, f, ensure_ascii=False, indent=2)

                with open(summary_path, "w", encoding="utf-8") as f:
                    json.dump(summary_record, f, ensure_ascii=False, indent=2)

                logger.info(f"记忆已保存: {memory_id}")
                return memory_id

            except Exception as e:
                logger.error(f"保存记忆失败: {e}")
                raise

    @classmethod
    def get_raw(cls, memory_id: str) -> dict | None:
        """通过 memory_id 获取原文记忆"""
        return cls._find_file(RAW_DIR, f"raw_{memory_id}.json")

    @classmethod
    def get_summary(cls, memory_id: str) -> dict | None:
        """通过 memory_id 获取摘要记忆"""
        return cls._find_file(SUMMARY_DIR, f"summary_{memory_id}.json")

    @classmethod
    def get_pair(cls, memory_id: str) -> tuple[dict | None, dict | None]:
        """通过 memory_id 同时获取原文和摘要"""
        return cls.get_raw(memory_id), cls.get_summary(memory_id)

    @classmethod
    def list_summaries(
        cls,
        limit: int = 50,
        offset: int = 0,
        topic: str | None = None,
        skill: str | None = None,
    ) -> list[dict]:
        """
        列出摘要记忆（支持筛选）

        Args:
            limit: 返回数量限制
            offset: 偏移量
            topic: 按主题筛选
            skill: 按技能筛选
        """
        summaries = []

        for path in sorted(SUMMARY_DIR.rglob("summary_*.json"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    record = json.load(f)

                if topic and topic not in record.get("topics", []):
                    continue
                if skill and skill not in record.get("selected_skills", []):
                    continue

                summaries.append(record)
            except Exception:
                continue

        # 按时间倒序
        summaries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return summaries[offset : offset + limit]

    @classmethod
    def get_session_summaries(cls, session_id: str, limit: int = 20) -> list[dict]:
        """
        获取指定会话的所有历史摘要记忆（按时间正序）

        Args:
            session_id: 会话ID
            limit: 最多返回条数

        Returns:
            摘要记忆列表（按时间正序，适合作为对话上下文）
        """
        summaries = []
        for path in SUMMARY_DIR.rglob("summary_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    record = json.load(f)
                if record.get("session_id") == session_id:
                    summaries.append(record)
            except Exception:
                continue

        summaries.sort(key=lambda x: x.get("timestamp", ""))
        return summaries[-limit:]

    @classmethod
    def get_session_raws(cls, session_id: str, limit: int = 20) -> list[dict]:
        """
        获取指定会话的所有原文记忆（按时间正序）

        Args:
            session_id: 会话ID
            limit: 最多返回条数

        Returns:
            原文记忆列表（按时间正序）
        """
        raws = []
        for path in RAW_DIR.rglob("raw_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    record = json.load(f)
                if record.get("session_id") == session_id:
                    raws.append(record)
            except Exception:
                continue

        raws.sort(key=lambda x: x.get("timestamp", ""))
        return raws[-limit:]

    @classmethod
    def build_context_from_summaries(
        cls,
        session_id: str,
        max_turns: int = 5,
        include_raw_on_demand: bool = True,
    ) -> tuple[str, list[dict]]:
        """
        从会话历史摘要构建对话上下文

        Args:
            session_id: 当前会话ID
            max_turns: 最多携带几轮历史摘要
            include_raw_on_demand: 是否标记可获取原文的记忆

        Returns:
            (context_text, referenced_memories)
            context_text: 格式化后的上下文文本
            referenced_memories: 引用的记忆列表（含 memory_id，供后续获取原文）
        """
        summaries = cls.get_session_summaries(session_id, limit=max_turns)
        if not summaries:
            return "", []

        lines = ["【历史对话摘要】"]
        referenced = []

        for i, summary in enumerate(summaries, 1):
            memory_id = summary.get("memory_id", "")
            query = summary.get("query_summary", "")
            response = summary.get("response_summary", "")
            skills = ", ".join(summary.get("selected_skills", []))
            conclusion = summary.get("conclusion", "")[:200]
            key_points = summary.get("key_points", [])
            skill_summaries = summary.get("skill_summaries", {})

            lines.append(f"\n--- 历史对话 {i} ---")
            lines.append(f"用户问题：{query}")
            lines.append(f"思考视角：{skills}")
            if key_points:
                lines.append(f"关键要点：{'；'.join(key_points[:5])}")
            if conclusion:
                lines.append(f"核心结论：{conclusion}")
            if response:
                lines.append(f"回复摘要：{response[:300]}")
            if skill_summaries:
                for sid, ssum in skill_summaries.items():
                    lines.append(f"  · {sid}：{ssum}")

            ref = {
                "memory_id": memory_id,
                "index": i,
                "query_summary": query,
                "conclusion": conclusion,
            }

            if include_raw_on_demand and len(response) < 50:
                ref["needs_raw"] = True

            referenced.append(ref)

        lines.append("\n--- 历史对话摘要结束 ---\n")
        return "\n".join(lines), referenced

    @classmethod
    def retrieve_relevant_raw_memories(
        cls,
        query: str,
        referenced_memories: list[dict],
        max_raw: int = 2,
    ) -> list[dict]:
        """
        根据当前问题，从已引用的记忆中智能选择需要获取原文的

        Args:
            query: 当前用户问题
            referenced_memories: 已引用的摘要记忆列表
            max_raw: 最多获取几条原文

        Returns:
            原文记忆列表
        """
        if not referenced_memories:
            return []

        query_lower = query.lower()
        scored = []

        for ref in referenced_memories:
            memory_id = ref.get("memory_id", "")
            if not memory_id:
                continue

            # 计算当前问题与历史摘要的相关度
            searchable = " ".join([
                ref.get("query_summary", ""),
                ref.get("conclusion", ""),
            ]).lower()

            score = 0
            if query_lower in searchable:
                score += searchable.count(query_lower) * 10

            # 如果之前标记了需要原文，加分
            if ref.get("needs_raw"):
                score += 5

            # 越新的记忆权重越高
            score += ref.get("index", 0)

            if score > 0:
                scored.append((score, memory_id))

        # 按分数排序，取前 max_raw 个
        scored.sort(key=lambda x: x[0], reverse=True)
        selected_ids = [mid for _, mid in scored[:max_raw]]

        raw_memories = []
        for memory_id in selected_ids:
            raw = cls.get_raw(memory_id)
            if raw:
                raw_memories.append(raw)

        return raw_memories

    @classmethod
    def build_raw_context(cls, raw_memories: list[dict]) -> str:
        """
        将原文记忆格式化为上下文文本

        Args:
            raw_memories: 原文记忆列表

        Returns:
            格式化后的原文上下文
        """
        if not raw_memories:
            return ""

        lines = ["【相关历史对话原文】"]

        for i, raw in enumerate(raw_memories, 1):
            query = raw.get("user_query", "")
            response = raw.get("full_response", "")
            synthesis = raw.get("synthesis", "")

            lines.append(f"\n--- 原文 {i} ---")
            lines.append(f"用户问题：{query}")

            if synthesis:
                lines.append(f"综合结论：{synthesis[:500]}")
            else:
                lines.append(f"完整回复：{response[:800]}")

            # 如果有辩论轮次，提取关键发言
            turns = raw.get("turns", [])
            if turns:
                lines.append("关键发言：")
                for turn in turns[:3]:
                    skill = turn.get("skill_id", "").replace("-perspective", "")
                    speech = turn.get("speech", "")[:200]
                    if skill and speech:
                        lines.append(f"  [{skill}] {speech}...")

        lines.append("\n--- 相关历史对话原文结束 ---\n")
        return "\n".join(lines)

    @classmethod
    def search_by_query(cls, query: str, top_k: int = 5) -> list[dict]:
        """
        简单文本搜索：在摘要记忆中搜索匹配 query 的记录

        Args:
            query: 搜索关键词
            top_k: 返回数量

        Returns:
            匹配的摘要记忆列表
        """
        matches = []
        query_lower = query.lower()

        for path in SUMMARY_DIR.rglob("summary_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    record = json.load(f)

                # 在多个字段中搜索
                searchable = " ".join([
                    record.get("query_summary", ""),
                    record.get("response_summary", ""),
                    " ".join(record.get("key_points", [])),
                    record.get("conclusion", ""),
                    " ".join(record.get("topics", [])),
                ]).lower()

                if query_lower in searchable:
                    # 计算简单相关度分数
                    score = searchable.count(query_lower)
                    record["_search_score"] = score
                    matches.append(record)

            except Exception:
                continue

        # 按相关度分数排序
        matches.sort(key=lambda x: x.get("_search_score", 0), reverse=True)
        return matches[:top_k]

    @classmethod
    def delete(cls, memory_id: str) -> bool:
        """删除一对记忆（原文+摘要）"""
        deleted = False
        for base_dir in (RAW_DIR, SUMMARY_DIR):
            for path in base_dir.rglob(f"*{memory_id}*.json"):
                try:
                    path.unlink()
                    deleted = True
                except Exception as e:
                    logger.warning(f"删除记忆文件失败: {e}")
        return deleted

    @classmethod
    def _find_file(cls, base_dir: Path, filename: str) -> dict | None:
        """在目录树中查找文件"""
        for path in base_dir.rglob(filename):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # 文本处理工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize_text(text: str, max_length: int = 200) -> str:
        """简单文本摘要：取前 max_length 字符，在句号处截断"""
        if len(text) <= max_length:
            return text.strip()

        truncated = text[:max_length]
        # 在最后一个句号处截断
        last_period = truncated.rfind("。")
        if last_period > max_length * 0.5:
            return truncated[: last_period + 1].strip()
        return truncated.strip() + "..."

    @staticmethod
    def _extract_key_points(text: str, max_points: int = 5) -> list[str]:
        """从文本中提取关键要点（基于常见标记）"""
        points = []

        # 匹配 "1. xxx" 或 "- xxx" 或 "* xxx" 格式的列表项
        patterns = [
            r"^\s*[\d一二三四五六七八九十]+[.、)）]\s*(.+?)$",
            r"^\s*[-•*]\s*(.+?)$",
            r"[。！？]\s*(?:关键|要点|核心|首先|其次|最后|总之|因此|建议)([^。！？]{10,80})[。！？]",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for match in matches:
                point = match.strip() if isinstance(match, str) else match[0].strip()
                if len(point) > 10 and point not in points:
                    points.append(point)
                if len(points) >= max_points:
                    break
            if len(points) >= max_points:
                break

        return points[:max_points]

    @staticmethod
    def _summarize_skill_outputs(skill_outputs: list[dict]) -> dict[str, str]:
        """为每个 skill 的输出生成一句话摘要"""
        summaries = {}
        for output in skill_outputs:
            skill_id = output.get("skill_id", "")
            suggestion = output.get("suggestion", "")
            if skill_id and suggestion:
                # 取前 100 字作为摘要
                summaries[skill_id] = suggestion[:100] + "..." if len(suggestion) > 100 else suggestion
        return summaries

    @staticmethod
    def _extract_conclusion(text: str) -> str:
        """提取结论部分"""
        conclusion_markers = [
            "综上所述", "总之", "总而言之", "最终建议", "总结",
            "综合以上", "给用户的建议", "辩证综合",
        ]

        for marker in conclusion_markers:
            idx = text.find(marker)
            if idx >= 0:
                conclusion = text[idx : idx + 300]
                # 在下一个大标题前截断
                next_heading = re.search(r"\n#{1,3}\s", text[idx + len(marker) :])
                if next_heading:
                    conclusion = text[idx : idx + len(marker) + next_heading.start()]
                return conclusion.strip()

        #  fallback：返回最后一段
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if paragraphs:
            return paragraphs[-1][:300]
        return text[:300]

    @staticmethod
    def _extract_topics(query: str, response: str) -> list[str]:
        """提取主题标签（基于关键词匹配）"""
        topic_keywords = {
            "职场": ["工作", "职场", "老板", "同事", "辞职", "升职", "面试", "加班", "薪资"],
            "人际关系": ["朋友", "人际", "关系", "相处", "矛盾", "沟通", "社交", "家庭"],
            "情感": ["爱情", "恋爱", "婚姻", "分手", "感情", "伴侣", "相亲", "离婚"],
            "学业": ["学习", "考试", "考研", "专业", "学校", "成绩", "论文", "毕业"],
            "人生抉择": ["选择", "抉择", "方向", "迷茫", "目标", "规划", "人生"],
            "财富": ["钱", "财富", "投资", "理财", "买房", "创业", "赚钱", "经济"],
            "健康": ["健康", "身体", "疾病", "养生", "运动", "饮食", "睡眠"],
            "心理": ["焦虑", "抑郁", "压力", "情绪", "心理", "心态", "自信", "恐惧"],
            "伦理": ["道德", "伦理", "善恶", "正义", "责任", "诚信", "公平"],
        }

        combined_text = (query + " " + response).lower()
        matched_topics = []

        for topic, keywords in topic_keywords.items():
            if any(kw in combined_text for kw in keywords):
                matched_topics.append(topic)

        return matched_topics[:5]
