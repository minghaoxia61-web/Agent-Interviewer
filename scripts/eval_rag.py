"""RAG 检索评测：多引擎 recall@5 / MRR 对比。

用法：
    ./.venv/Scripts/python.exe scripts/eval_rag.py

引擎覆盖：
- ngram：始终可用（字符 n-gram Jaccard）
- bm25：始终可用（纯 Python Okapi BM25）
- chroma：已安装 chromadb 时可用；默认 embedding 模型首次使用需联网下载，
  或配置 LLM_API_KEY 相关 embedding 服务后使用。

结果写入 data/eval/rag_report.md。
"""
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.rag.retriever import build_retriever  # noqa: E402

QUERIES = json.loads((ROOT / "data" / "eval" / "rag_queries.json").read_text(encoding="utf-8"))
TOP_K = 5


def eval_engine(name, retriever):
    hits, rr, latencies = 0, 0.0, []
    for item in QUERIES:
        expect = set(item["expect"])
        t0 = time.perf_counter()
        results = retriever.search(item["q"], top_k=TOP_K)
        latencies.append((time.perf_counter() - t0) * 1000)
        ids = [e.id for e in results]
        if any(i in expect for i in ids):
            hits += 1
        for rank, i in enumerate(ids, 1):
            if i in expect:
                rr += 1.0 / rank
                break
    n = len(QUERIES)
    return {
        "engine": name,
        "recall@5": hits / n,
        "mrr": rr / n,
        "avg_ms": round(sum(latencies) / len(latencies), 2),
    }


def main():
    lines = ["# RAG 检索评测报告", "",
             f"- 查询集：{len(QUERIES)} 条标注查询（data/eval/rag_queries.json）",
             f"- 指标：recall@{TOP_K}（前 5 命中任一标注题）、MRR（标注题平均倒数排名）", ""]
    rows = []

    for engine in ("ngram", "bm25", "chroma"):
        try:
            r = build_retriever(ROOT / "data" / "knowledge", engine,
                                chroma_dir=Path(tempfile.mkdtemp(prefix="rai_eval_chroma_")))
            if r.name != engine:
                rows.append({"engine": engine, "recall@5": "-", "mrr": "-",
                             "avg_ms": "-", "note": f"初始化失败回落 {r.name}"})
                continue
            m = eval_engine(engine, r)
            m["note"] = ""
            rows.append(m)
        except Exception as e:  # noqa: BLE001
            rows.append({"engine": engine, "recall@5": "-", "mrr": "-",
                         "avg_ms": "-", "note": f"不可用：{str(e)[:60]}"})

    lines += ["| 引擎 | recall@5 | MRR | 平均耗时(ms) | 备注 |", "| --- | --- | --- | --- | --- |"]
    for row in rows:
        lines.append(f"| {row['engine']} | {row['recall@5']} | {row['mrr']} | {row['avg_ms']} | {row['note']} |")

    active = build_retriever(ROOT / "data" / "knowledge", "auto",
                             chroma_dir=Path(tempfile.mkdtemp(prefix="rai_eval_auto_")))
    lines += ["", f"- 当前配置（RETRIEVER_MODE=auto）实际启用：**{active.name}**", ""]
    lines.append("> chroma 默认内置 embedding 模型对中文偏弱且首次使用需联网下载；"
                 "生产建议配置 OpenAI 兼容 embedding 服务后重跑本脚本对比。")

    out = ROOT / "data" / "eval" / "rag_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
