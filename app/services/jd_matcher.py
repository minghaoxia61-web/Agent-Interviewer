"""JD 对比诊断：岗位描述 vs 简历的确定性匹配（可解释，LLM 失败时的兜底）。"""
import re
from typing import Any, Dict, List

TECH_KEYWORDS = [
    # 语言
    "Python", "Go", "Java", "C++", "TypeScript", "JavaScript", "Rust", "SQL", "Shell",
    # 后端 / 存储
    "FastAPI", "Django", "Flask", "Spring", "gRPC", "Redis", "MySQL", "MongoDB",
    "PostgreSQL", "Elasticsearch", "ClickHouse", "Kafka", "RabbitMQ", "RocketMQ", "消息队列",
    # 架构 / 工程
    "微服务", "分布式", "高并发", "高可用", "缓存", "限流", "熔断", "消息推送", "网关",
    "Docker", "Kubernetes", "K8s", "CI/CD", "Linux", "单元测试", "监控", "灰度",
    # 数据 / 算法
    "数据结构", "算法", "LeetCode", "机器学习", "深度学习", "PyTorch", "TensorFlow",
    "Spark", "Flink", "Hive", "数仓", "ETL", "Pandas", "Hadoop",
    # 前端
    "React", "Vue", "Webpack", "Vite", "性能优化", "组件化", "跨端", "小程序",
    # 通用素质
    "沟通", "协作", " owner", "Owner", "主导", "跨团队", "文档", "Code Review",
]

# 归一化别名（JD 里可能出现的写法 → 统一关键词）
_ALIASES = {"k8s": "Kubernetes", "kubernetes": "Kubernetes", "js": "JavaScript", "ts": "TypeScript"}


def extract_jd_keywords(jd_text: str, limit: int = 20) -> List[str]:
    """从 JD 文本中提取命中的技术关键词（按 JD 中出现顺序去重）。"""
    jd = jd_text or ""
    found: List[str] = []
    seen = set()
    for kw in TECH_KEYWORDS:
        if kw.lower() in jd.lower() and kw.lower() not in seen:
            seen.add(kw.lower())
            found.append(kw)
    # 附加：JD 中的英文技术词（大写驼峰/全大写，如 gRPC、OAuth）
    for m in re.findall(r"\b[A-Za-z][A-Za-z0-9+#.]{1,20}\b", jd):
        token = m.strip(".")
        if token.lower() in seen or len(token) < 3:
            continue
        if re.match(r"^[A-Z][a-z]+([A-Z][a-z0-9]+)+$|^[A-Z]{2,6}$", token) and not re.search(r"[\u4e00-\u9fff]", token):
            seen.add(token.lower())
            found.append(token)
        if len(found) >= limit:
            break
    return found[:limit]


def match_jd(jd_text: str, resume: Dict[str, Any], target_position: str = "") -> Dict[str, Any]:
    """确定性匹配：JD 关键词覆盖率 + 差距清单 + 补齐建议。"""
    keywords = extract_jd_keywords(jd_text)
    resume_text = " ".join(
        (resume.get("skills") or [])
        + [h for p in (resume.get("projects") or []) for h in (p.get("highlights") or [])]
        + (resume.get("experiences") or [])
    ).lower()

    matched = [kw for kw in keywords if kw.lower() in resume_text]
    missing = [kw for kw in keywords if kw not in matched]
    score = round(len(matched) / len(keywords) * 100) if keywords else 0

    suggestions: List[Dict[str, str]] = []
    for kw in missing[:5]:
        suggestions.append({
            "keyword": kw,
            "text": f"JD 强调「{kw}」，但简历中没有体现。若你实际掌握：把相关经历写进项目亮点并给出量化结果；"
                    f"若未掌握：面试前至少准备「概念 + 使用场景」，或诚实以基础原理切入。",
        })
    if not keywords:
        suggestions.append({"keyword": "关键词",
                            "text": "JD 中未识别到技术关键词，可检查文本是否完整粘贴。"})

    if score >= 70:
        summary = f"匹配度 {score}%：核心关键词覆盖良好，重点准备把匹配项讲深讲透。"
    elif score >= 40:
        summary = f"匹配度 {score}%：有 {len(missing)} 个 JD 关键词在简历中缺失，优先补齐出现频次最高的几项。"
    else:
        summary = f"匹配度 {score}%：简历与该 JD 重合度偏低，建议针对性改写简历或评估该岗位投递优先级。"

    return {
        "match_score": score,
        "keywords_total": len(keywords),
        "matched": matched,
        "missing": missing,
        "suggestions": suggestions,
        "summary": summary,
        "mode": "deterministic",
    }
