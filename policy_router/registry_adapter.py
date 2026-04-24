"""
DialecticEngine - Skill Registry Adapter
=========================================
负责从 skills/ 目录读取和解析 skill 元数据。

Registry Architecture:
- SkillRegistry: skill注册表，管理所有可用skill
- RegistryAdapter: 适配器，处理skill文件解析和元数据转换

Design:
- 懒加载：只在需要时加载skill元数据
- 增量更新：监视文件变化，动态更新注册表
- 缓存：缓存已解析的skill元数据
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import uuid

from .types import (
    SkillMetadata,
    QueryEmbedding,
    DomainTag,
    RouterConfig,
)


# ============================================================================
# YAML-FRONT MATTER PARSER
# ============================================================================


def parse_yaml_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.

    YAML frontmatter格式：
    ---
    key: value
    key2: |
      multi-line
      value
    ---

    Returns:
        Tuple of (metadata dict, body content)
    """
    # 匹配 YAML frontmatter
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        return {}, content

    yaml_str = match.group(1)
    body = match.group(2)

    # 简单YAML解析（处理基本类型）
    metadata = _parse_yaml_simple(yaml_str)

    return metadata, body


def _parse_yaml_simple(yaml_str: str) -> dict[str, Any]:
    """Simple YAML parser for frontmatter.

    支持：字符串、多行字符串、列表、布尔值、数字
    不支持：嵌套对象、复杂引用
    """
    result: dict[str, Any] = {}
    current_key: Optional[str] = None
    current_lines: list[str] = []

    for line in yaml_str.split('\n'):
        # 检查缩进（列表项或延续行）
        if line.startswith('  - ') or line.startswith('- '):
            # 列表项
            if current_key and current_lines:
                result[current_key] = '\n'.join(current_lines).strip()
            list_match = re.match(r'^\s*-\s*(.*)', line)
            if list_match:
                if current_key and isinstance(result.get(current_key), list):
                    result[current_key].append(list_match.group(1).strip())
                else:
                    current_key = None
                    current_lines = []
            continue

        # 检查键值对
        key_match = re.match(r'^(\w+):\s*(.*)$', line)
        if key_match:
            # 保存之前的键
            if current_key and current_lines:
                value = '\n'.join(current_lines).strip()
                if value.startswith('|'):
                    value = value[1:].strip()
                result[current_key] = value
            elif current_key:
                result[current_key] = True  # 布尔值（无值键）

            current_key = key_match.group(1)
            value = key_match.group(2).strip()

            if value.startswith('|'):
                # 多行字符串开始
                current_lines = []
            elif value:
                result[current_key] = _parse_yaml_value(value)
                current_key = None
            else:
                current_lines = []
        elif line.strip() and current_key:
            # 延续行
            if current_lines is not None:
                current_lines.append(line.strip())

    # 保存最后一个键
    if current_key and current_lines:
        value = '\n'.join(current_lines).strip()
        if value.startswith('|'):
            value = value[1:].strip()
        result[current_key] = value
    elif current_key:
        result[current_key] = True

    return result


def _parse_yaml_value(value: str) -> Any:
    """Parse YAML scalar value."""
    value = value.strip()

    # 布尔值
    if value in ('true', 'True', 'TRUE'):
        return True
    if value in ('false', 'False', 'FALSE'):
        return False

    # null
    if value in ('null', 'Null', 'NULL', '~'):
        return None

    # 数字
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # 去除引号
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]

    return value


# ============================================================================
# SKILL REGISTRY
# ============================================================================


class SkillRegistry:
    """Central registry for all skills.

    管理所有可用的skill，提供：
    - 动态加载/重载
    - 元数据缓存
    - 按标签/领域查询
    """

    def __init__(
        self,
        base_path: str = "skills",
        glob_pattern: str = "**/SKILL.md",
    ):
        self.base_path = Path(base_path)
        self.glob_pattern = glob_pattern

        # 缓存
        self._skills: dict[str, SkillMetadata] = {}
        self._last_scan: Optional[datetime] = None
        self._scan_interval_seconds: float = 60.0  # 60秒内不重复扫描

        # 按标签索引
        self._tag_index: dict[str, set[str]] = {}
        self._domain_index: dict[DomainTag, set[str]] = {}

    def scan(self, force: bool = False) -> list[SkillMetadata]:
        """Scan skills directory and load all skill metadata.

        Args:
            force: 强制重新扫描，忽略缓存

        Returns:
            List of all discovered skills
        """
        now = datetime.now(timezone.utc)

        # 避免频繁扫描
        if (
            not force
            and self._last_scan
            and (now - self._last_scan).total_seconds() < self._scan_interval_seconds
        ):
            return list(self._skills.values())

        self._last_scan = now

        # 查找所有SKILL.md文件
        skill_files = list(self.base_path.glob(self.glob_pattern))

        # 解析每个skill
        for skill_file in skill_files:
            try:
                skill = self._parse_skill_file(skill_file)
                if skill:
                    self._cache_skill(skill)
            except Exception as e:
                print(f"Warning: Failed to parse {skill_file}: {e}")
                continue

        return list(self._skills.values())

    def _parse_skill_file(self, file_path: Path) -> Optional[SkillMetadata]:
        """Parse a single SKILL.md file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return None

        # 解析frontmatter
        metadata, body = parse_yaml_frontmatter(content)

        if not metadata:
            # 没有frontmatter，尝试从文件名推断
            skill_name = file_path.parent.name
            description = self._extract_description_from_body(body[:500])
            tags = self._infer_tags_from_path(file_path)
        else:
            skill_name = metadata.get("name", file_path.parent.name)
            description = metadata.get("description", "")
            tags = set(metadata.get("tags", []))

        # 提取领域标签
        domains = self._map_tags_to_domains(tags)

        # 提取推理风格（从body中查找）
        reasoning_style = self._extract_reasoning_style(body)

        # 提取擅长/不擅长领域
        strengths, weaknesses = self._extract_strengths_weaknesses(body)

        # 生成skill ID
        skill_id = self._generate_skill_id(skill_name)

        return SkillMetadata(
            skill_id=skill_id,
            name=skill_name,
            slug=file_path.parent.name,
            tags=frozenset(tags),
            domains=domains,
            description=description[:500] if description else "",
            reasoning_style=reasoning_style,
            strengths=tuple(strengths),
            weaknesses=tuple(weaknesses),
            skill_file_path=str(file_path.absolute()),
            version=metadata.get("version", "1.0.0"),
        )

    def _cache_skill(self, skill: SkillMetadata) -> None:
        """Cache skill and update indices."""
        self._skills[skill.skill_id] = skill

        # 更新标签索引
        for tag in skill.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(skill.skill_id)

        # 更新领域索引
        for domain in skill.domains:
            if domain not in self._domain_index:
                self._domain_index[domain] = set()
            self._domain_index[domain].add(skill.skill_id)

    def _generate_skill_id(self, name: str) -> str:
        """Generate unique skill ID from name."""
        # 清理名称，生成slug
        slug = re.sub(r'[^a-zA-Z0-9]', '-', name.lower())
        slug = re.sub(r'-+', '-', slug).strip('-')
        return slug

    def _extract_description_from_body(self, body: str) -> str:
        """Extract description from skill body."""
        # 查找第一个段落
        lines = body.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                return line[:200]
        return ""

    def _infer_tags_from_path(self, file_path: Path) -> set[str]:
        """Infer tags from file path."""
        tags = set()

        # 从目录名推断
        parts = file_path.parts
        for part in parts:
            if 'perspective' in part:
                tags.add(part.replace('-perspective', ''))
            elif part in ['rujia', 'fajia', 'daojia', 'bingjia', 'mojia', 'mingjia']:
                tags.add(part)

        return tags

    def _map_tags_to_domains(self, tags: set[str]) -> frozenset[DomainTag]:
        """Map skill tags to domain tags."""
        tag_to_domain = {
            "rujia": {DomainTag.ETHICS, DomainTag.RELATIONSHIPS, DomainTag.SELF_CULTIVATION},
            "fajia": {DomainTag.LAW, DomainTag.GOVERNANCE},
            "daojia": {DomainTag.NATURE, DomainTag.METAPHYSICS},
            "bingjia": {DomainTag.STRATEGY},
            "mojia": {DomainTag.LOGIC, DomainTag.ETHICS},
            "mingjia": {DomainTag.LOGIC},
            "yinyangjia": {DomainTag.NATURE},
            "zonghengjia": {DomainTag.RHETORIC, DomainTag.STRATEGY},
            "zajia": {DomainTag.DIALECTICS},
            "jingxue": {DomainTag.METAPHYSICS},
            "xuanxue": {DomainTag.METAPHYSICS, DomainTag.NATURE},
            "chan": {DomainTag.METAPHYSICS},
            "lixue": {DomainTag.METAPHYSICS, DomainTag.ETHICS},
            "xinxue": {DomainTag.SELF_CULTIVATION, DomainTag.METAPHYSICS},
        }

        domains: set[DomainTag] = set()
        for tag in tags:
            if tag in tag_to_domain:
                domains.update(tag_to_domain[tag])

        return frozenset(domains) if domains else frozenset({DomainTag.ETHICS})

    def _extract_reasoning_style(self, body: str) -> str:
        """Extract reasoning style description from body."""
        # 查找"核心心智模型"或"推理风格"部分
        patterns = [
            r'## 核心心智模型.*?(?=##|\Z)',
            r'## 决策启发式.*?(?=##|\Z)',
            r'## 表达DNA.*?(?=##|\Z)',
        ]

        for pattern in patterns:
            match = re.search(pattern, body, re.DOTALL)
            if match:
                section = match.group(0)
                # 提取前200字符
                text = re.sub(r'[#>*`]', '', section)[:200]
                return text.strip()

        return "综合分析"

    def _extract_strengths_weaknesses(
        self,
        body: str,
    ) -> tuple[list[str], list[str]]:
        """Extract strengths and weaknesses from body."""
        strengths: list[str] = []
        weaknesses: list[str] = []

        # 查找"擅长"和"不擅长"部分
        strength_match = re.search(
            r'\*\*擅长\*\*[：:]\s*(.*?)(?=\*\*|$)',
            body,
            re.DOTALL
        )
        if strength_match:
            text = strength_match.group(1)
            strengths = [s.strip() for s in text.split('\n') if s.strip()]

        weakness_match = re.search(
            r'\*\*不擅长\*\*[：:]\s*(.*?)(?=\*\*|$)',
            body,
            re.DOTALL
        )
        if weakness_match:
            text = weakness_match.group(1)
            weaknesses = [s.strip() for s in text.split('\n') if s.strip()]

        return strengths, weaknesses

    # -------------------------------------------------------------------------
    # QUERY METHODS
    # -------------------------------------------------------------------------

    def get_all_skills(self) -> list[SkillMetadata]:
        """Get all registered skills."""
        if not self._skills:
            self.scan()
        return list(self._skills.values())

    def get_skill(self, skill_id: str) -> Optional[SkillMetadata]:
        """Get skill by ID."""
        if not self._skills:
            self.scan()
        return self._skills.get(skill_id)

    def get_skills_by_tag(self, tag: str) -> list[SkillMetadata]:
        """Get all skills with a specific tag."""
        if not self._skills:
            self.scan()

        skill_ids = self._tag_index.get(tag, set())
        return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    def get_skills_by_domain(self, domain: DomainTag) -> list[SkillMetadata]:
        """Get all skills in a specific domain."""
        if not self._skills:
            self.scan()

        skill_ids = self._domain_index.get(domain, set())
        return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    def search_skills(self, query: str) -> list[SkillMetadata]:
        """Search skills by name or description."""
        if not self._skills:
            self.scan()

        query_lower = query.lower()
        results: list[tuple[SkillMetadata, int]] = []

        for skill in self._skills.values():
            score = 0
            if query_lower in skill.name.lower():
                score += 3
            if query_lower in skill.description.lower():
                score += 2
            if any(query_lower in tag for tag in skill.tags):
                score += 1

            if score > 0:
                results.append((skill, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in results]

    def reload(self) -> list[SkillMetadata]:
        """Force reload all skills."""
        self._skills.clear()
        self._tag_index.clear()
        self._domain_index.clear()
        return self.scan(force=True)


# ============================================================================
# REGISTRY ADAPTER
# ============================================================================


class RegistryAdapter:
    """Adapter for bridging registry and router.

    提供更高层的接口，简化router与registry的交互。
    """

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        config: Optional[RouterConfig] = None,
    ):
        self.config = config or RouterConfig()
        self.registry = registry or SkillRegistry(
            base_path=self.config.skills_base_path,
            glob_pattern=self.config.skills_glob_pattern,
        )

    def get_skills_for_scoring(self) -> list[SkillMetadata]:
        """Get all skills ready for scoring."""
        return self.registry.get_all_skills()

    def get_skill_metadata(self, skill_id: str) -> Optional[SkillMetadata]:
        """Get metadata for a specific skill."""
        return self.registry.get_skill(skill_id)

    def get_skills_by_domains(self, domains: frozenset) -> list[SkillMetadata]:
        """Get skills matching any of the given domains."""
        results: list[SkillMetadata] = []
        for domain in domains:
            results.extend(self.registry.get_skills_by_domain(domain))
        return results

    def get_skill_embedding(self, skill_id: str) -> Optional[QueryEmbedding]:
        """Get pre-computed embedding for a skill (if available)."""
        skill = self.registry.get_skill(skill_id)
        if skill and skill.embedding:
            return skill.embedding
        return None

    def get_skill_info_for_explanation(
        self,
        skill_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Get skill info formatted for explanation generation."""
        info: dict[str, dict[str, Any]] = {}

        for skill_id in skill_ids:
            skill = self.registry.get_skill(skill_id)
            if skill:
                info[skill_id] = {
                    "name": skill.name,
                    "description": skill.description[:200],
                    "strengths": list(skill.strengths)[:3],
                }

        return info


# ============================================================================
# FACTORY
# ============================================================================


def create_registry(
    base_path: Optional[str] = None,
    config: Optional[RouterConfig] = None,
) -> SkillRegistry:
    """Factory function to create skill registry."""
    config = config or RouterConfig()
    base = base_path or config.skills_base_path
    return SkillRegistry(
        base_path=base,
        glob_pattern=config.skills_glob_pattern,
    )


def create_adapter(
    registry: Optional[SkillRegistry] = None,
    config: Optional[RouterConfig] = None,
) -> RegistryAdapter:
    """Factory function to create registry adapter."""
    return RegistryAdapter(registry=registry, config=config)
