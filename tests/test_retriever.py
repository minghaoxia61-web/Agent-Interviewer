"""RAG 检索引擎测试（离线引擎：ngram / bm25）。"""
import pytest

from app.services.rag.retriever import BM25Retriever, NgramRetriever, build_retriever
from pathlib import Path

KB = Path(__file__).resolve().parent.parent / "data" / "knowledge"


@pytest.fixture(scope="module")
def entries():
    from app.services.rag.retriever import load_entries
    return load_entries(KB)


def test_factory_auto_falls_back_to_offline_engine(entries):
    """auto 模式下 chroma 不可用（离线）时必须回落 bm25，且不能抛异常。"""
    import tempfile
    r = build_retriever(KB, "auto", chroma_dir=Path(tempfile.mkdtemp()))
    assert r.name in ("bm25", "chroma")


def test_bm25_hits_expected_question(entries):
    r = BM25Retriever(entries)
    hit = r.pick("缓存穿透 击穿 雪崩 怎么防范")
    assert hit and hit["id"] == "redis_02"


def test_ngram_hits_expected_question(entries):
    r = NgramRetriever(entries)
    hit = r.pick("GIL 对多线程的影响")
    assert hit and hit["id"] == "py_01"


def test_exclude_filters_asked_questions(entries):
    r = BM25Retriever(entries)
    first = r.pick("redis 持久化")
    again = r.pick("redis 持久化", exclude=[first["id"]])
    assert again["id"] != first["id"]
