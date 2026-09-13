"""简历 → markdown 渲染（agent-context-overhaul Phase 2.2）。

DbBackend 用它把 `resumes.extracted_content` 按需渲染成 `/resume/active.md`，
替代原先"解析后写 profile.md / stable_facts"的落盘投影。

对字段缺失容错：解析结果由 LLM 产出，任何 section 都可能缺；缺就跳过，
不抛异常（抛了会中断 agent 循环）。
"""
from __future__ import annotations

from typing import Any


def _as_list(value: Any) -> list[Any]:
    """skills 等字段可能是 list，也可能是逗号分隔字符串"""
    if not value:
        return []
    if isinstance(value, list):
        return [v for v in value if v]
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    return [value]


def _field(entry: dict, *names: str) -> str:
    """按优先级取第一个非空字段（兼容 position/title 这类别名）"""
    for name in names:
        val = entry.get(name)
        if val:
            return str(val)
    return ""


def render_resume_markdown(extracted_content: dict | None) -> str:
    """把简历解析结果渲染成给 agent 读的 markdown 视图。"""
    data = extracted_content or {}
    lines: list[str] = ["# 当前生效简历", ""]

    info = data.get("personal_info") or {}
    basic_parts = [
        f"{label}: {info[key]}"
        for key, label in (
            ("name", "姓名"),
            ("location", "所在地"),
            ("email", "邮箱"),
            ("phone", "电话"),
        )
        if info.get(key)
    ]
    if basic_parts:
        lines += ["## 基本信息", "、".join(basic_parts), ""]

    education = data.get("education") or []
    if education:
        lines.append("## 教育背景")
        for edu in education[:3]:
            if not isinstance(edu, dict):
                continue
            parts = [
                _field(edu, "school"),
                _field(edu, "degree"),
                _field(edu, "major"),
            ]
            period = _field(edu, "period") or " ".join(
                x for x in (_field(edu, "start_date"), _field(edu, "end_date")) if x
            )
            text = " - ".join(p for p in parts if p)
            lines.append(f"- {text}{'（' + period + '）' if period else ''}")
        lines.append("")

    work = data.get("work_experience") or []
    if work:
        lines.append("## 工作经历")
        for job in work[:5]:
            if not isinstance(job, dict):
                continue
            head = " - ".join(
                p
                for p in (
                    _field(job, "company"),
                    _field(job, "position", "title"),
                )
                if p
            )
            period = _field(job, "period") or " ".join(
                x for x in (_field(job, "start_date"), _field(job, "end_date")) if x
            )
            lines.append(f"- {head}{'（' + period + '）' if period else ''}")
            desc = _field(job, "description", "responsibilities", "summary")
            if desc:
                # 压成单行，避免破坏列表结构
                lines.append(f"  {desc.replace(chr(10), ' ').strip()}")
        lines.append("")

    projects = data.get("projects") or []
    if projects:
        lines.append("## 项目经历")
        for proj in projects[:5]:
            if not isinstance(proj, dict):
                continue
            name = _field(proj, "name", "project", "title")
            desc = _field(proj, "description", "summary")
            lines.append(f"- {name}{'：' + desc.replace(chr(10), ' ').strip() if desc else ''}")
        lines.append("")

    skills = _as_list(data.get("skills"))
    if skills:
        lines += ["## 技能", ", ".join(str(s) for s in skills[:20]), ""]

    if len(lines) <= 2:
        # 解析结果为空/全不可用：给明确提示而不是空文件
        return "（简历已上传但暂无可用的解析结果，建议重新解析或手动补全画像）\n"

    return "\n".join(lines)
