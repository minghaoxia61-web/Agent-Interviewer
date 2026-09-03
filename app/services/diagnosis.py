"""简历诊断：从"找漏洞"升级为结构化体检报告。

评分与建议由确定性启发式计算（Mock 模式，可解释）；
真实 LLM 模式走 RESUME_DIAGNOSE_SYSTEM，失败自动回落到启发式。
"""
import re
from typing import Any, Dict, List

DIMENSIONS = [
    ("quantified", "量化程度"),
    ("project_depth", "项目深度"),
    ("keyword_match", "岗位关键词匹配"),
    ("clarity", "表述清晰度"),
    ("completeness", "信息完整度"),
]
DIM_LABELS = dict(DIMENSIONS)

# 按岗位大类匹配的关键词集（命中越多分越高）
POSITION_KEYWORDS = {
    "后端": ["Redis", "MySQL", "消息队列", "Kafka", "Docker", "Kubernetes", "Linux",
           "高并发", "分布式", "缓存", "微服务", "API", "SQL", "索引", "事务"],
    "前端": ["React", "Vue", "TypeScript", "Webpack", "Vite", "性能优化", "组件",
           "浏览器", "HTTP", "CSS", "工程化", "状态管理"],
    "算法": ["机器学习", "深度学习", "PyTorch", "TensorFlow", "特征工程", "模型",
           "数据结构", "LeetCode", "论文", "竞赛"],
    "数据": ["SQL", "Hive", "Spark", "Flink", "数仓", "ETL", "埋点", "指标", "Python"],
    "测试": ["自动化测试", "Selenium", "Pytest", "用例", "压测", "CI/CD", "质量"],
}
DEFAULT_KEYWORDS = POSITION_KEYWORDS["后端"]

ACTION_VERBS = re.compile(r"设计|实现|搭建|优化|主导|重构|封装|落地|独立完成|从 0|从0|推动")
SECTION_KEYS = {"name": "基本信息", "skills": "技能清单", "projects": "项目经历",
                "experiences": "实习/工作", "education": "教育背景"}


def _clamp(x: float) -> float:
    return round(max(1.0, min(10.0, x)), 1)


def _keywords_for(position: str) -> List[str]:
    for key, kws in POSITION_KEYWORDS.items():
        if key in (position or ""):
            return kws
    return DEFAULT_KEYWORDS


def diagnose(resume: Dict[str, Any], target_position: str) -> Dict[str, Any]:
    projects = resume.get("projects") or []
    highlights = [h for p in projects for h in (p.get("highlights") or [])]
    skills = resume.get("skills") or []
    n_h = len(highlights) or 1

    quant = sum(1 for h in highlights if re.search(r"\d", h))
    quantified = _clamp(quant / n_h * 10)

    per_project = n_h / max(len(projects), 1)
    project_depth = _clamp(min(10.0, len(projects) * 2.2 + per_project * 1.4))

    text = " ".join(skills + highlights)
    kw_hits = sum(1 for kw in _keywords_for(target_position) if kw.lower() in text.lower())
    keyword_match = _clamp(min(10.0, kw_hits / 7 * 10))

    verb = sum(1 for h in highlights if ACTION_VERBS.search(h))
    clarity = _clamp(2.5 + verb / n_h * 7.5)

    present = sum(1 for k in ("name", "skills", "projects", "experiences", "education")
                  if resume.get(k))
    completeness = _clamp(present / 5 * 10)

    scores = {
        "quantified": quantified, "project_depth": project_depth,
        "keyword_match": keyword_match, "clarity": clarity,
        "completeness": completeness,
    }
    overall = round(sum(scores.values()) / len(scores) * 10)

    suggestions: List[Dict[str, str]] = []
    if quantified < 6:
        suggestions.append({
            "dimension": "quantified",
            "text": "项目亮点缺少数字支撑：给每条亮点补上规模（QPS/数据量/用户数）或收益（RT 下降 xx%、错误率降低 xx%），例如把「优化了查询」改写成「通过覆盖索引把 P99 从 900ms 降到 80ms」。",
        })
    if project_depth < 6:
        suggestions.append({
            "dimension": "project_depth",
            "text": "项目数量/厚度不足：保留 1-2 个最有含金量的项目，按「背景 → 你的方案 → 关键取舍 → 结果」四段式重写，删掉一句话带过的小项目。",
        })
    if keyword_match < 6:
        suggestions.append({
            "dimension": "keyword_match",
            "text": f"与岗位关键词匹配度偏低：对照 {target_position or '目标岗位'} JD 补充你真实掌握的技术栈关键词（如缓存、消息队列、容器化），但不要堆砌没做过的名词。",
        })
    if clarity < 6:
        suggestions.append({
            "dimension": "clarity",
            "text": "表述偏被动/模糊：把「参与、协助」换成「设计、实现、主导」，并写清你本人负责的边界与产出物。",
        })
    if completeness < 8:
        missing = [label for k, label in SECTION_KEYS.items() if not resume.get(k)]
        suggestions.append({
            "dimension": "completeness",
            "text": f"信息完整度待补齐：缺少 {('、'.join(missing))} 模块，教育经历与实习经历即使简短也应保留时间线。",
        })
    if not suggestions:
        suggestions.append({
            "dimension": "quantified",
            "text": "整体结构良好。冲刺大厂简历时可以再补充：项目的线上验证数据、你遇到的最难的一个 bug 及排查过程。",
        })

    if overall >= 80:
        comment = "简历竞争力较强，量化与结构都在水准之上，可以直接约模拟面试检验被追问的承受力。"
    elif overall >= 60:
        comment = "简历有基础但细节不够扎实，建议先按下方建议打磨一轮，再进模拟面试验证。"
    else:
        comment = "简历目前经不起深挖，优先补量化数据和明确的个人职责，避免面试官第一轮就失去兴趣。"

    return {"scores": scores, "overall": overall, "comment": comment,
            "suggestions": suggestions, "mode": "heuristic"}
