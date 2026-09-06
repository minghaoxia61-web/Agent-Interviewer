"""API 全链路测试：上传 → 异步分析 → 面试 → 报告，投递看板 CRUD，鉴权护栏。"""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


def _sample_bytes() -> bytes:
    return (Path(__file__).resolve().parent.parent / "data" / "samples"
            / "sample_resume.md").read_bytes()


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _upload(client, position="后端开发工程师"):
    r = client.post("/api/resume/upload",
                    files={"file": ("sample_resume.md", _sample_bytes(), "text/markdown")},
                    data={"target_position": position})
    assert r.status_code == 200
    data = r.json()
    # 挖掘/诊断在后台线程并行执行，轮询直到完成（Mock 模式毫秒级）
    for _ in range(80):
        a = client.get(f"/api/resume/{data['session_id']}/analysis").json()
        if a["analysis_status"] == "done":
            data.update(weaknesses=a["weaknesses"], diagnosis=a["diagnosis"])
            return data
        time.sleep(0.25)
    raise AssertionError("简历分析超时未完成")


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_upload_returns_analysis_state_then_diagnosis(client):
    data = _upload(client)
    assert data["session_id"]
    assert len(data["weaknesses"]) >= 1
    assert data["diagnosis"]["overall"] >= 0
    assert set(data["diagnosis"]["scores"]) >= {"quantified", "clarity"}


def test_analysis_endpoint_states(client):
    r = client.post("/api/resume/upload",
                    files={"file": ("sample_resume.md", _sample_bytes(), "text/markdown")},
                    data={"target_position": "后端开发工程师"})
    sid = r.json()["session_id"]
    # 上传即刻返回，分析异步执行：轮询到完成
    deadline = time.time() + 15
    while time.time() < deadline:
        a = client.get(f"/api/resume/{sid}/analysis").json()
        if a["analysis_status"] == "done":
            break
        time.sleep(0.25)
    assert a["analysis_status"] == "done"
    assert a["weaknesses"]
    # 完成后开始面试不应再报 409
    assert client.post(f"/api/interview/{sid}/start").status_code == 200


def test_interview_flow_vague_triggers_followup(client):
    sid = _upload(client)["session_id"]
    assert client.post(f"/api/interview/{sid}/start").status_code == 200

    r = client.post(f"/api/interview/{sid}/message",
                    json={"message": "我叫张三，做过校园二手交易平台和分布式爬虫。"})
    assert r.json()["stage"] == "project_probing"

    vague = client.post(f"/api/interview/{sid}/message",
                        json={"message": "就大概做了下，效果还行。"}).json()
    assert vague["decision"] == "follow_up"
    assert vague["probe_depth"] == 1
    assert vague["decision_reasons"], "追问必须携带可证伪的触发原因"

    solid = client.post(f"/api/interview/{sid}/message", json={"message": (
        "因为压测发现基线接口平均 RT 是 250ms，定位后发现 80% 耗时在重复查询，"
        "于是把热点数据放进 Redis 并设置 5 分钟 TTL，改造后压测 RT 降到 45ms")}).json()
    assert solid["decision"] in ("advance", "advance_stage")


def test_finish_generates_report(client):
    sid = _upload(client)["session_id"]
    client.post(f"/api/interview/{sid}/start")
    client.post(f"/api/interview/{sid}/message",
                json={"message": "我叫张三，做过校园二手交易平台。"})
    rep = client.post(f"/api/interview/{sid}/finish").json()
    assert rep["markdown"].startswith("# RAI")
    assert len(rep["scores"]) == 5
    got = client.get(f"/api/report/{sid}").json()
    assert got["overall"] == rep["overall"]


def test_state_includes_messages_for_resume(client):
    sid = _upload(client)["session_id"]
    client.post(f"/api/interview/{sid}/start")
    client.post(f"/api/interview/{sid}/message",
                json={"message": "我叫张三，做过校园二手交易平台。"})
    st = client.get(f"/api/interview/{sid}/state").json()
    assert st["total_turns"] == 1
    assert len(st["messages"]) >= 3  # 开场 + 用户 + 追问


def test_board_crud(client):
    created = client.post("/api/applications", json={
        "company": "测试公司", "position": "后端", "status": "applied"}).json()
    app_id = created["id"]

    moved = client.put(f"/api/applications/{app_id}", json={"status": "interview"}).json()
    assert moved["status"] == "interview"
    assert [t["status"] for t in moved["timeline"]] == ["applied", "interview"]

    listing = client.get("/api/applications").json()
    assert any(i["id"] == app_id for i in listing["items"])

    assert client.delete(f"/api/applications/{app_id}").status_code == 200
    assert client.delete(f"/api/applications/{app_id}").status_code == 404


def test_jd_match_endpoint(client):
    sid = _upload(client)["session_id"]
    r = client.post(f"/api/resume/{sid}/jd-match", json={
        "jd": "负责高并发后端服务，使用 Python/Redis/Kafka，熟悉 MySQL 与 Docker。"})
    assert r.status_code == 200
    data = r.json()
    assert 0 <= data["match_score"] <= 100
    assert data["matched"], "示例简历与该 JD 应有命中关键词"


def test_access_token_guard(client, monkeypatch):
    """配置令牌后：无令牌 401，带令牌 200；未配置时全放行。"""
    monkeypatch.setattr(settings, "access_token", "test-token-123")
    assert client.get("/api/workbench/dashboard").status_code == 401
    assert client.get("/api/workbench/dashboard",
                      headers={"X-API-Token": "test-token-123"}).status_code == 200
    assert client.get("/api/workbench/dashboard?token=test-token-123").status_code == 200
    # 错误令牌
    assert client.get("/api/workbench/dashboard",
                      headers={"X-API-Token": "wrong"}).status_code == 401


def test_visitor_isolation(client):
    """不同访客的数据互相不可见（隐私隔离）。"""
    sid = _upload(client)["session_id"]
    # 其他访客访问 → 404（不泄露存在性）
    assert client.get(f"/api/interview/{sid}/state",
                      headers={"X-Visitor-Id": "visitor-b"}).status_code == 404
    # 属主正常访问
    assert client.get(f"/api/interview/{sid}/state").status_code == 200
    # 仪表盘按访客过滤
    assert client.get("/api/workbench/dashboard").json()["session_count"] >= 1
    assert client.get("/api/workbench/dashboard",
                      headers={"X-Visitor-Id": "visitor-b"}).json()["session_count"] == 0


def test_board_isolation(client):
    aid = client.post("/api/applications",
                      json={"company": "A公司", "position": "后端"},
                      headers={"X-Visitor-Id": "visitor-a"}).json()["id"]
    assert client.get("/api/applications",
                      headers={"X-Visitor-Id": "visitor-b"}).json()["total"] == 0
    assert client.put(f"/api/applications/{aid}", json={"status": "offer"},
                      headers={"X-Visitor-Id": "visitor-b"}).status_code == 404
    assert client.delete(f"/api/applications/{aid}",
                         headers={"X-Visitor-Id": "visitor-a"}).status_code == 200


def test_ws_stream_start_and_message(client):
    sid = _upload(client)["session_id"]
    with client.websocket_connect(f"/ws/interview/{sid}?vid=anonymous") as ws:
        ws.send_json({"type": "start"})
        frames = []
        while True:
            f = ws.receive_json()
            frames.append(f)
            if f["type"] == "final":
                break
    assert any(f["type"] == "token" for f in frames), "开场必须流式输出 token 帧"
    assert frames[-1]["assistant_message"]
    assert frames[-1]["stage"] == "project_probing"


def test_jd_history_accumulates(client):
    sid = _upload(client)["session_id"]
    jd = "负责高并发后端服务，使用 Python/Redis/Kafka，熟悉 MySQL 与 Docker。"
    r1 = client.post(f"/api/resume/{sid}/jd-match", json={"jd": jd}).json()
    r2 = client.post(f"/api/resume/{sid}/jd-match",
                     json={"jd": jd + "加分项：有 Kubernetes 与 gRPC 实践。"}).json()
    assert r1["history"] is not None and r2["history"] is not None
    assert len(r2["history"]) == 2, "两次分析应产生两条历史记录"
    assert all("match_score" in h for h in r2["history"])
