"""端到端冒烟测试：Mock 模式下跑通 上传 -> 开场 -> 追问 -> 推进 -> 报告 -> Trace 全链路。

用法：./.venv/Scripts/python.exe scripts/smoke_test.py
（使用 fastapi TestClient 进程内执行，不占用端口）
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SAMPLE = ROOT / "data" / "samples" / "sample_resume.md"

SOLID_ANSWER = (
    "因为我们在优化前先用 wrk 压测拿到基线：接口平均 RT 是 250ms，P99 达到 900ms。"
    "定位发现 80% 的耗时在 3 个重复查询上，于是把热点数据放进 Redis 并设置 5 分钟 TTL，"
    "同时用兜底随机过期避免缓存同时失效。改造后压测 RT 降到 45ms，报告存在内部压测平台。"
)

client = TestClient(app)


def check(name: str, cond: bool, extra: str = "") -> None:
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" —— {extra}" if extra else ""))
    if not cond:
        raise SystemExit(f"冒烟测试失败：{name}")


def main() -> None:
    # 1. 健康检查
    r = client.get("/api/health")
    check("health", r.status_code == 200 and r.json()["status"] == "ok",
          f"llm_mode={r.json().get('llm_mode')}")

    # 2. 上传简历（Markdown）
    r = client.post("/api/resume/upload",
                    files={"file": ("sample_resume.md", SAMPLE.read_bytes(), "text/markdown")},
                    data={"target_position": "后端开发工程师"})
    check("upload", r.status_code == 200, f"status={r.status_code}")
    data = r.json()
    sid = data["session_id"]
    check("weaknesses_dug", len(data["weaknesses"]) >= 1,
          f"{len(data['weaknesses'])} 个疑点: " + "; ".join(w["quote"][:18] for w in data["weaknesses"]))

    # 3. 开场
    r = client.post(f"/api/interview/{sid}/start")
    check("start", r.status_code == 200 and len(r.json()["assistant_message"]) > 20)
    print(f"    面试官: {r.json()['assistant_message'][:48]}...")

    # 4. 自我介绍 -> 第一个疑点提问
    r = client.post(f"/api/interview/{sid}/message",
                    json={"message": "面试官你好，我叫张三，做过校园二手交易平台和分布式爬虫，主要用 Python 和 Redis。"})
    check("probe_question", r.status_code == 200 and r.json()["stage"] == "project_probing")
    print(f"    面试官: {r.json()['assistant_message'][:48]}...")

    # 5. 含糊回答 -> 触发追问
    r = client.post(f"/api/interview/{sid}/message",
                    json={"message": "就大概做了下，效果还行。"})
    j = r.json()
    check("follow_up_triggered", j["decision"] == "follow_up" and j["probe_depth"] == 1,
          f"decision={j['decision']} reasons={j['decision_reasons']}")
    print(f"    面试官(追问): {j['assistant_message'][:48]}...")

    # 6. 扎实回答 -> 逐步推进直至自然结束
    stages_seen = {"project_probing"}
    finished_naturally = False
    for i in range(30):
        r = client.post(f"/api/interview/{sid}/message", json={"message": SOLID_ANSWER})
        j = r.json()
        stages_seen.add(j["stage"])
        if j["finished"]:
            finished_naturally = True
            break
    check("stage_progression",
          {"tech_drill", "stress_test"}.issubset(stages_seen),
          f"经过阶段: {sorted(stages_seen)}")
    check("natural_finish", finished_naturally, f"共 {i + 1} 轮后自然结束")

    # 7. 报告
    r = client.get(f"/api/report/{sid}")
    j = r.json()
    check("report_scores", len(j["scores"]) == 5 and 0 <= j["overall"] <= 10,
          f"overall={j['overall']}")
    check("report_markdown", "综合得分" in j["markdown"] and "追问复盘" in j["markdown"])
    check("report_persisted", (ROOT / "data" / "reports" / f"{sid}.md").exists())
    check("trace_persisted", (ROOT / "data" / "traces" / f"{sid}.jsonl").exists()
          and len((ROOT / "data" / "traces" / f"{sid}.jsonl").read_text(encoding="utf-8").strip().splitlines()) >= 6)

    # 8. WebSocket 流式（新会话）
    r = client.post("/api/resume/upload",
                    files={"file": ("sample_resume.md", SAMPLE.read_bytes(), "text/markdown")},
                    data={"target_position": "后端开发工程师"})
    sid2 = r.json()["session_id"]
    with client.websocket_connect(f"/ws/interview/{sid2}") as ws:
        ws.send_json({"type": "start"})
        tokens, final = [], None
        while True:
            frame = ws.receive_json()
            if frame["type"] == "token":
                tokens.append(frame["data"])
            elif frame["type"] == "final":
                final = frame
                break
        check("ws_start_stream", len(tokens) >= 3 and final is not None,
              f"{len(tokens)} 个 token 片段")
        ws.send_json({"type": "message", "data": "我做过一个校园二手交易平台，我负责后端。"})
        tokens2 = 0
        while True:
            frame = ws.receive_json()
            if frame["type"] == "token":
                tokens2 += 1
            elif frame["type"] in ("final", "error"):
                break
        check("ws_message_stream", tokens2 >= 1 and frame["type"] == "final",
              f"{tokens2} 个 token 片段")

    print("\n=== 全部冒烟测试通过 ===")


if __name__ == "__main__":
    main()
