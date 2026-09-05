"""JD 匹配与简历诊断的确定性引擎测试。"""
from app.services.diagnosis import diagnose
from app.services.jd_matcher import extract_jd_keywords, match_jd

JD = """岗位职责：负责核心后端服务开发，保障高并发高可用。
使用 Go/Python 构建微服务，涉及 Redis 缓存、Kafka 消息队列、MySQL。
参与 Kubernetes 容器化部署与 CI/CD 建设。熟悉 gRPC、Elasticsearch。"""

RESUME = {
    "skills": ["Python", "MySQL", "Redis", "Docker"],
    "projects": [{
        "name": "校园平台", "role": "后端", "period": "2024",
        "stack": ["FastAPI", "MySQL"],
        "highlights": [
            "通过引入 Redis 缓存把接口平均响应时间降低了 80%",
            "使用 Celery 处理异步任务，支撑日均 10w 消息",
            "参与数据库优化，查询性能提升 300%",
        ],
    }],
    "experiences": ["某公司后端实习生"],
    "education": ["XX大学 本科"],
}


def test_extract_keywords_from_jd():
    kws = extract_jd_keywords(JD)
    assert "Python" in kws and "Redis" in kws and "Kafka" in kws
    assert len(kws) <= 20


def test_match_jd_score_bounds_and_gaps():
    result = match_jd(JD, RESUME, "后端开发工程师")
    assert 0 <= result["match_score"] <= 100
    assert set(result["matched"]) | set(result["missing"]) == set(result["matched"]) | set(result["missing"])
    assert not (set(result["matched"]) & set(result["missing"]))
    assert result["suggestions"], "缺失关键词时必须给出补齐建议"
    assert result["mode"] in ("deterministic", "mock", "heuristic", "llm")


def test_diagnosis_scores_and_suggestions():
    result = diagnose(RESUME, "后端开发工程师")
    assert set(result["scores"].keys()) == {
        "quantified", "project_depth", "keyword_match", "clarity", "completeness"}
    assert all(1.0 <= v <= 10.0 for v in result["scores"].values())
    assert 0 <= result["overall"] <= 100
    assert result["suggestions"], "必须给出至少一条建议"
    assert result["comment"]
