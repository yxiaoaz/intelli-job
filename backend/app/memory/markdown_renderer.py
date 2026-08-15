"""Markdown 渲染层 — DB ↔ markdown 双向投影。

markdown 是 cache + agent 工作内存，字段名严格按 Pydantic schema。
"""
import re
from datetime import datetime
from typing import Optional

from app.memory.schemas import (
    UserMemory,
    SessionMemory,
    JobPreference,
    SalaryRange,
)
from app.utils.logger import get_logger

logger = get_logger()


# ── Render ─────────────────────────────────────────────────────────────────

def render_user_memory(memory: UserMemory) -> str:
    """UserMemory → markdown string"""
    lines = ["# 用户长期画像", ""]

    # Metadata
    lines.append("## Metadata")
    lines.append(f"- last_updated: {memory.last_updated.isoformat() if memory.last_updated else 'N/A'}")
    lines.append("")

    # stable_facts
    lines.append("## 稳定事实 (stable_facts)")
    if memory.stable_facts:
        for k, v in memory.stable_facts.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- (空)")
    lines.append("")

    # long_term_preferences
    prefs = memory.long_term_preferences
    lines.append("## 长期偏好 (long_term_preferences)")
    lines.extend(_render_job_preference(prefs))
    lines.append("")

    # negative_signals
    lines.append("## 负面信号 (negative_signals)")
    if memory.negative_signals:
        for s in memory.negative_signals:
            lines.append(f"- {s}")
    else:
        lines.append("- (空)")
    lines.append("")

    # career_direction
    lines.append("## 求职方向 (career_direction)")
    lines.append(memory.career_direction or "(未设定)")
    lines.append("")

    return "\n".join(lines)


def render_session_memory(memory: SessionMemory) -> str:
    """SessionMemory → markdown string"""
    lines = ["# 对话状态", ""]

    # Metadata
    lines.append("## Metadata")
    lines.append(f"- last_updated: {memory.last_updated.isoformat() if memory.last_updated else 'N/A'}")
    lines.append("")

    # current_goal
    lines.append("## 目标 (current_goal)")
    lines.append(memory.current_goal or "auto")
    lines.append("")

    # preferences
    lines.append("## 偏好 (preferences)")
    lines.extend(_render_job_preference(memory.preferences))
    lines.append("")

    # preference_sources
    lines.append("## 偏好来源 (preference_sources)")
    if memory.preference_sources:
        for k, v in memory.preference_sources.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- (空)")
    lines.append("")

    # open_questions
    lines.append("## 待回答问题 (open_questions)")
    if memory.open_questions:
        for q in memory.open_questions:
            lines.append(f"- {q}")
    else:
        lines.append("- (空)")
    lines.append("")

    # recent_decisions
    lines.append("## 近期决策 (recent_decisions)")
    if memory.recent_decisions:
        for d in memory.recent_decisions:
            lines.append(f"- {d}")
    else:
        lines.append("- (空)")
    lines.append("")

    # next_action
    lines.append("## 建议的 next_action")
    lines.append(memory.next_action or "(无)")
    lines.append("")

    return "\n".join(lines)


def _render_job_preference(prefs: JobPreference) -> list[str]:
    """渲染 JobPreference 为 markdown 行列表"""
    lines = []
    if prefs.target_roles:
        lines.append(f"- target_roles: {', '.join(prefs.target_roles)}")
    if prefs.locations:
        lines.append(f"- locations: {', '.join(prefs.locations)}")
    if prefs.salary:
        lines.append(f"- salary:")
        lines.append(f"  - min: {prefs.salary.min}")
        if prefs.salary.max:
            lines.append(f"  - max: {prefs.salary.max}")
        lines.append(f"  - currency: {prefs.salary.currency}")
    if prefs.recruitment_types:
        lines.append(f"- recruitment_types: {', '.join(prefs.recruitment_types)}")
    if prefs.industries:
        lines.append(f"- industries: {', '.join(prefs.industries)}")
    if prefs.target_companies:
        lines.append(f"- target_companies: {', '.join(prefs.target_companies)}")
    if prefs.target_company_types:
        lines.append(f"- target_company_types: {', '.join(prefs.target_company_types)}")
    if prefs.skills:
        lines.append(f"- skills: {', '.join(prefs.skills)}")
    if not lines:
        lines.append("- (空)")
    return lines


# ── Parse ──────────────────────────────────────────────────────────────────

def parse_user_memory(content: str) -> Optional[UserMemory]:
    """markdown → UserMemory（尽力解析，失败返回 None）"""
    try:
        sections = _split_sections(content)

        # Metadata
        meta = sections.get("metadata", "")
        last_updated = _extract_meta_field(meta, "last_updated")
        last_updated_dt = datetime.fromisoformat(last_updated) if last_updated and last_updated != "N/A" else None

        # stable_facts
        sf_text = sections.get("稳定事实 (stable_facts)", "")
        stable_facts = _parse_kv_list(sf_text)

        # long_term_preferences
        prefs_text = sections.get("长期偏好 (long_term_preferences)", "")
        prefs = _parse_job_preference(prefs_text)

        # negative_signals
        ns_text = sections.get("负面信号 (negative_signals)", "")
        negative_signals = _parse_simple_list(ns_text)

        # career_direction
        cd_text = sections.get("求职方向 (career_direction)", "").strip()
        career_direction = cd_text if cd_text and cd_text != "(未设定)" else None

        return UserMemory(
            stable_facts=stable_facts,
            long_term_preferences=prefs,
            negative_signals=negative_signals,
            career_direction=career_direction,
            last_updated=last_updated_dt,
        )
    except Exception as e:
        logger.warning("parse_user_memory_failed", error=str(e))
        return None


def parse_session_memory(content: str) -> Optional[SessionMemory]:
    """markdown → SessionMemory（尽力解析，失败返回 None）"""
    try:
        sections = _split_sections(content)

        # Metadata
        meta = sections.get("metadata", "")
        last_updated = _extract_meta_field(meta, "last_updated")
        last_updated_dt = datetime.fromisoformat(last_updated) if last_updated and last_updated != "N/A" else None

        # current_goal
        cg_text = sections.get("目标 (current_goal)", "").strip()
        current_goal = cg_text if cg_text else "auto"

        # preferences
        prefs_text = sections.get("偏好 (preferences)", "")
        prefs = _parse_job_preference(prefs_text)

        # preference_sources
        ps_text = sections.get("偏好来源 (preference_sources)", "")
        preference_sources = _parse_kv_list(ps_text)

        # open_questions
        oq_text = sections.get("待回答问题 (open_questions)", "")
        open_questions = _parse_simple_list(oq_text)

        # recent_decisions
        rd_text = sections.get("近期决策 (recent_decisions)", "")
        recent_decisions = _parse_simple_list(rd_text)

        # next_action
        na_text = sections.get("建议的 next_action", "").strip()
        next_action = na_text if na_text and na_text != "(无)" else None

        return SessionMemory(
            current_goal=current_goal,
            preferences=prefs,
            preference_sources=preference_sources,
            open_questions=open_questions,
            recent_decisions=recent_decisions,
            next_action=next_action,
            last_updated=last_updated_dt,
        )
    except Exception as e:
        logger.warning("parse_session_memory_failed", error=str(e))
        return None


# ── Helpers ────────────────────────────────────────────────────────────────

def _split_sections(content: str) -> dict[str, str]:
    """按 ## 标题拆分 markdown 为 {标题: 内容} 字典"""
    sections: dict[str, str] = {}
    current_key = ""
    current_lines: list[str] = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_key:
                sections[current_key.lower()] = "\n".join(current_lines).strip()
            current_key = line[3:].strip()
            current_lines = []
        elif line.startswith("# "):
            # 跳过 H1
            continue
        else:
            current_lines.append(line)

    if current_key:
        sections[current_key.lower()] = "\n".join(current_lines).strip()

    return sections


def _extract_meta_field(text: str, field: str) -> Optional[str]:
    """从 metadata 段提取 `- field: value`"""
    for line in text.split("\n"):
        line = line.strip().lstrip("- ").strip()
        if line.startswith(f"{field}:"):
            return line[len(field) + 1:].strip()
    return None


def _parse_simple_list(text: str) -> list[str]:
    """解析 `- item` 列表"""
    items = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- ") and not line.startswith("- ("):
            items.append(line[2:].strip())
    return items


def _parse_kv_list(text: str) -> dict:
    """解析 `- key: value` 为 dict"""
    result = {}
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- ") and ":" in line and not line.startswith("- ("):
            content = line[2:]
            key, _, value = content.partition(":")
            result[key.strip()] = value.strip()
    return result


def _parse_job_preference(text: str) -> JobPreference:
    """从 markdown 段解析 JobPreference"""
    data: dict = {}
    salary_data: dict = {}
    in_salary = False

    for line in text.split("\n"):
        # 检测嵌套 salary 子项（以空格开头的 `  - key: value`）
        if in_salary and line.startswith("  - "):
            sub = line.strip()[2:]  # 去掉 `- ` 前缀
            if ":" in sub:
                k, _, v = sub.partition(":")
                k = k.strip()
                v = v.strip()
                if k in ("min", "max"):
                    try:
                        salary_data[k] = int(v)
                    except ValueError:
                        pass
                elif k == "currency":
                    salary_data[k] = v
            continue
        else:
            if in_salary:
                in_salary = False

        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        content = stripped[2:]

        if ":" not in content:
            continue

        key, _, value = content.partition(":")
        key = key.strip()
        value = value.strip()

        if key == "salary":
            in_salary = True
            continue

        # 逗号分隔的 list 字段
        if key in (
            "target_roles", "locations", "recruitment_types",
            "industries", "target_companies", "target_company_types", "skills",
        ):
            data[key] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            data[key] = value

    if salary_data:
        data["salary"] = salary_data

    return JobPreference(**data)
