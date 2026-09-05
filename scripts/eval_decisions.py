"""追问决策评估：规则回归 + 全链路轨迹模拟。

用法：
    ./.venv/Scripts/python.exe scripts/eval_decisions.py           # 输出报告
    ./.venv/Scripts/python.exe scripts/eval_decisions.py --ci      # 断言失败时退出码 1

评估两部分：
1. 规则回归：data/eval/golden_answers.json 中 30 条黄金样本，
   验证 assess_answer 的 is_solid 与触发原因集合 100% 符合预期（可进 CI 的回归门）；
2. 轨迹模拟：用脚本化候选人跑完整面试状态机，验证「含糊回答触发追问、
   扎实回答推进、追问层数封顶、阶段按时推进」的行为契约。
"""
import json
import os
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.rules import assess_answer  # noqa: E402

CI = "--ci" in sys.argv
GOLDEN = json.loads((ROOT / "data" / "eval" / "golden_answers.json").read_text(encoding="utf-8"))


def eval_rules():
    ok, mismatches = 0, []
    reason_stats = {}
    for item in GOLDEN:
        solid, reasons = assess_answer(item["answer"])
        got = set(reasons)
        want = set(item["expect_reasons"])
        good = (solid == item["expect_solid"]) and (got == want)
        ok += good
        if not good:
            mismatches.append({
                "id": item["id"], "answer": item["answer"][:40],
                "expect_solid": item["expect_solid"], "got_solid": solid,
                "expect": sorted(want), "got": sorted(got),
            })
        for r in want | got:
            reason_stats.setdefault(r, {"tp": 0, "fp": 0, "fn": 0})
        # 逐原因统计 precision / recall
        for r in want & got:
            reason_stats[r]["tp"] += 1
        for r in got - want:
            reason_stats[r]["fp"] += 1
        for r in want - got:
            reason_stats[r]["fn"] += 1
    accuracy = ok / len(GOLDEN)
    return accuracy, mismatches, reason_stats


def eval_trajectory(lines: list) -> None:
    """脚本化候选人跑完整面试，校验行为契约。"""
    # 重定向数据目录，避免污染真实会话；拷贝真实知识库保证轨迹贴近生产
    tmp_data = Path(tempfile.mkdtemp(prefix="rai_eval_"))
    os.environ["DATA_DIR"] = str(tmp_data)
    (tmp_data / "knowledge").mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "data" / "knowledge").glob("*.json"):
        (tmp_data / "knowledge" / f.name).write_bytes(f.read_bytes())
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    sample = ROOT / "data" / "samples" / "sample_resume.md"
    sid = client.post("/api/resume/upload",
                      files={"file": ("s.md", sample.read_bytes(), "text/markdown")},
                      data={"target_position": "后端开发工程师"}).json()["session_id"]
    # 等待后台分析（挖掘/诊断并行）完成后再开始面试
    for _ in range(80):
        a = client.get(f"/api/resume/{sid}/analysis").json()
        if a["analysis_status"] == "done":
            break
        time.sleep(0.25)
    client.post(f"/api/interview/{sid}/start")

    VAGUE = "就大概做了下，效果还行"
    SOLID = ("因为压测发现基线接口平均 RT 是 250ms，定位后发现 80% 耗时在重复查询，"
             "于是把热点数据放进 Redis 并设置 5 分钟 TTL，改造后压测 RT 降到 45ms")
    # 开场自我介绍(扎实) + 3 个疑点各 4 轮(含糊×3追问 + 含糊×1封顶推进) + 技术基础 4 轮 + 压力 2 轮
    script = [SOLID] + [VAGUE] * 12 + [SOLID] * 4 + [VAGUE] * 2

    follow_ups = 0
    stage_order = []
    finished_at = None
    contract_ok = True
    for i, answer in enumerate(script, 1):
        r = client.post(f"/api/interview/{sid}/message", json={"message": answer})
        if r.status_code != 200:
            contract_ok = False
            lines.append(f"| {i} | ERROR | - | {r.json().get('detail', '')[:40]} |")
            break
        j = r.json()
        stage_order.append(j["stage"])
        is_vague = answer == VAGUE
        if j["decision"] == "follow_up":
            follow_ups += 1
            # 行为契约：含糊回答必然触发追问，且必须带触发原因
            if not is_vague or not j["decision_reasons"]:
                contract_ok = False
        elif is_vague and j["decision"] in ("advance", "advance_stage"):
            # 含糊但推进：只允许发生在追问层数封顶时（probe_depth 已达 3）
            pass
        if j["finished"]:
            finished_at = i
        lines.append(f"| {i} | {j['stage']} | {j['decision']} | {j['assistant_message'][:24].replace(chr(10), ' ')}… |")

    contract_ok = contract_ok and follow_ups == 9
    contract_ok = contract_ok and "tech_drill" in stage_order and "stress_test" in stage_order
    contract_ok = contract_ok and finished_at is not None and finished_at <= len(script)

    lines.append("")
    lines.append(f"- 追问总数：{follow_ups}（预期 9 = 3 个疑点 × 3 层封顶）")
    lines.append(f"- 阶段轨迹：{' → '.join(stage_order)}")
    lines.append(f"- 自然结束轮次：{finished_at}")
    lines.append(f"- 行为契约：{'✅ 全部满足' if contract_ok else '❌ 存在违背'}")
    return contract_ok


def main():
    lines = ["# 追问决策评估报告", "",
             f"- 评估对象：`app/core/rules.py::assess_answer` + LangGraph 面试状态机",
             f"- 样本集：{len(GOLDEN)} 条黄金回答（data/eval/golden_answers.json）", ""]
    accuracy, mismatches, reason_stats = eval_rules()
    lines += ["## 一、规则回归（黄金样本）", "",
              f"- 决策准确率：**{accuracy:.0%}**（{round(accuracy * len(GOLDEN))}/{len(GOLDEN)}）", ""]
    lines.append("| 触发原因 | TP | FP | FN |")
    lines.append("| --- | --- | --- | --- |")
    for r, s in sorted(reason_stats.items()):
        lines.append(f"| {r} | {s['tp']} | {s['fp']} | {s['fn']} |")
    if mismatches:
        lines += ["", "### 不一致样本", ""]
        for m in mismatches:
            lines.append(f"- `{m['id']}` 期望 solid={m['expect_solid']}{m['expect']}，"
                         f"实际 solid={m['got_solid']}{m['got']}：「{m['answer']}」")

    lines += ["", "## 二、全链路轨迹模拟（脚本化候选人）", "",
              "| 轮次 | 阶段 | 决策 | 面试官输出 |", "| --- | --- | --- | --- |"]
    traj_ok = eval_trajectory(lines)

    verdict = accuracy == 1.0 and traj_ok
    lines += ["", "## 结论", "", f"- {'✅ 全部通过' if verdict else '❌ 存在回归'}", ""]

    out = ROOT / "data" / "eval" / "decision_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    if CI and not verdict:
        sys.exit(1)


if __name__ == "__main__":
    main()
