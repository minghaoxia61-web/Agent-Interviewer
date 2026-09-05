"""大厂面经知识库检索（RAG）：三种可切换后端 + 统一评测口径。

- NgramRetriever  字符 n-gram Jaccard（v1 基线，纯 Python）
- BM25Retriever   经典 BM25（纯 Python 零依赖，默认）
- ChromaRetriever ChromaDB 持久化向量检索（需安装 chromadb；首次调用会下载内置 embedding 模型）

settings.retriever_mode: auto / bm25 / ngram / chroma
auto = 优先 Chroma（可用时），否则 BM25；Chroma 初始化失败自动回落 BM25。
评测脚本 evals/retrieval_eval.py 用同一批查询对三种后端做 recall@k 对比。
"""
import json
import math
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    id: str
    company: str = "通用"
    category: str = "综合"
    question: str
    keywords: List[str] = Field(default_factory=list)


def load_entries(knowledge_dir: Path) -> List[KnowledgeEntry]:
    entries: List[KnowledgeEntry] = []
    if not knowledge_dir.exists():
        return entries
    for f in sorted(knowledge_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        items = data if isinstance(data, list) else data.get("entries", [])
        for i, item in enumerate(items):
            try:
                if not item.get("id"):
                    item["id"] = f"{f.stem}_{i}"
                entries.append(KnowledgeEntry(**item))
            except Exception:  # noqa: BLE001 - 单条脏数据不阻塞启动
                continue
    return entries


def _grams(s: str) -> List[str]:
    """中文按二元组、ASCII 按词切分（检索与评测统一用这个口径）。"""
    s = re.sub(r"\s+", " ", s.lower())
    grams: List[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]+", s):
        if len(run) == 1:
            grams.append(run)
        else:
            grams.extend(run[i : i + 2] for i in range(len(run) - 1))
    grams.extend(re.findall(r"[a-z0-9]+", s))
    return grams


class BaseRetriever:
    name = "base"

    def __init__(self, entries: List[KnowledgeEntry]) -> None:
        self.entries = entries

    def search(self, query: str, top_k: int = 1,
               exclude: Optional[List[str]] = None) -> List[KnowledgeEntry]:
        raise NotImplementedError

    def pick(self, query: str, exclude: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        hits = self.search(query, top_k=1, exclude=exclude)
        return hits[0].model_dump() if hits else None


class NgramRetriever(BaseRetriever):
    """v1 基线：字符 n-gram Jaccard + 关键词加权。"""

    name = "ngram"

    def search(self, query: str, top_k: int = 1,
               exclude: Optional[List[str]] = None) -> List[KnowledgeEntry]:
        exclude = exclude or []
        q_grams = set(_grams(query))
        scored: List[Any] = []
        for e in self.entries:
            if e.id in exclude:
                continue
            score = 0.0
            for kw in e.keywords:
                if kw.lower() in query.lower():
                    score += 3.0
            t_grams = set(_grams(e.question + " " + " ".join(e.keywords)))
            union = len(q_grams | t_grams)
            if union:
                score += 4.0 * len(q_grams & t_grams) / union
            scored.append((score, e))
        scored.sort(key=lambda x: (-x[0], x[1].id))
        return [e for _, e in scored[:top_k]]


class BM25Retriever(BaseRetriever):
    """经典 BM25（Okapi），纯 Python 实现。"""

    name = "bm25"

    def __init__(self, entries: List[KnowledgeEntry], k1: float = 1.5, b: float = 0.75) -> None:
        super().__init__(entries)
        self.k1, self.b = k1, b
        docs = [(_grams(e.question + " " + " ".join(e.keywords)), e) for e in entries]
        self._docs = docs
        self._avgdl = sum(len(d) for d, _ in docs) / max(len(docs), 1)
        df: Counter = Counter()
        for d, _ in docs:
            df.update(set(d))
        self._idf = {t: math.log((len(docs) - n + 0.5) / (n + 0.5) + 1.0) for t, n in df.items()}

    def search(self, query: str, top_k: int = 1,
               exclude: Optional[List[str]] = None) -> List[KnowledgeEntry]:
        exclude = exclude or []
        q_grams = _grams(query)
        scored: List[Any] = []
        for d, e in self._docs:
            if e.id in exclude:
                continue
            tf = Counter(d)
            dl = len(d)
            score = 0.0
            for t in set(q_grams):
                if t not in tf:
                    continue
                score += self._idf.get(t, 0.0) * tf[t] * (self.k1 + 1) / (
                    tf[t] + self.k1 * (1 - self.b + self.b * dl / self._avgdl))
            # 关键词整串命中给额外加权（BM25 对短英文词不敏感）
            for kw in e.keywords:
                if kw.lower() in query.lower():
                    score += 2.5
            scored.append((score, e))
        scored.sort(key=lambda x: (-x[0], x[1].id))
        return [e for _, e in scored[:top_k]]


class ChromaRetriever(BaseRetriever):
    """ChromaDB 持久化向量检索。初始化失败（未安装/离线无法下载模型）由工厂回落。"""

    name = "chroma"

    def __init__(self, entries: List[KnowledgeEntry], persist_dir: Path) -> None:
        super().__init__(entries)
        import chromadb

        self.client = chromadb.PersistentClient(path=str(persist_dir))
        col_name = "rai_interview_questions"
        existing = {c.name for c in self.client.list_collections()}
        if col_name in existing:
            self.col = self.client.get_collection(col_name)
        else:
            self.col = self.client.create_collection(col_name, metadata={"hnsw:space": "cosine"})
        if self.col.count() != len(entries):  # 知识库变化时重建
            self.client.delete_collection(col_name)
            self.col = self.client.create_collection(col_name, metadata={"hnsw:space": "cosine"})
            self.col.add(
                ids=[e.id for e in entries],
                documents=[f"{e.question} {' '.join(e.keywords)} {e.company} {e.category}" for e in entries],
            )
        # 预热：强制在初始化阶段加载/校验 embedding 通路（内置模型需联网下载）。
        # 否则空集合时 init 成功、第一次 query 才因模型下载失败而崩溃，错误来得太晚。
        try:
            self.col.query(query_texts=["warmup"], n_results=min(1, max(self.col.count(), 1)))
        except Exception as e:  # noqa: BLE001 - 转成 init 失败，交由工厂回落 BM25
            raise RuntimeError(f"chroma embedding 预热失败: {e}") from e

    def search(self, query: str, top_k: int = 1,
               exclude: Optional[List[str]] = None) -> List[KnowledgeEntry]:
        exclude = exclude or []
        by_id = {e.id: e for e in self.entries}
        res = self.col.query(query_texts=[query], n_results=min(top_k + len(exclude),
                                                                max(self.col.count(), 1)))
        out: List[KnowledgeEntry] = []
        for doc_id in (res.get("ids") or [[]])[0]:
            if doc_id in exclude or doc_id not in by_id:
                continue
            out.append(by_id[doc_id])
            if len(out) >= top_k:
                break
        return out


def build_retriever(knowledge_dir: Path, mode: str = "auto",
                    chroma_dir: Optional[Path] = None) -> BaseRetriever:
    """按配置构建检索器；chroma 初始化失败自动回落 bm25。"""
    entries = load_entries(knowledge_dir)
    mode = (mode or "auto").lower()

    def _try_chroma(timeout: float = 20.0) -> Optional[ChromaRetriever]:
        """Chroma 初始化加硬超时：首次使用会联网下载内置 embedding 模型，
        离线/弱网时可能长时间阻塞，超时即回落 BM25，避免拖慢服务启动。"""
        global _chroma_unavailable
        if chroma_dir is None or _chroma_unavailable:
            return None
        result: Dict[str, Optional[ChromaRetriever]] = {}

        def _build() -> None:
            try:
                result["r"] = ChromaRetriever(entries, chroma_dir)
            except Exception as e:  # noqa: BLE001 - 未安装/离线等一切原因都回落
                print(f"[RAI] Chroma 检索初始化失败，回落 BM25：{e}")
                result["r"] = None

        t = threading.Thread(target=_build, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            print(f"[RAI] Chroma 检索初始化超时（>{timeout:.0f}s，通常为离线下载模型卡住），回落 BM25")
            _chroma_unavailable = True
            return None
        if result.get("r") is None:
            _chroma_unavailable = True
        return result.get("r")

    if mode == "ngram":
        return NgramRetriever(entries)
    if mode == "bm25":
        return BM25Retriever(entries)
    if mode == "chroma":
        r = _try_chroma()
        if r:
            return r
        return BM25Retriever(entries)
    # auto
    r = _try_chroma()
    if r:
        return r
    return BM25Retriever(entries)


# 兼容旧导入名
Retriever = NgramRetriever

# 进程级记忆：Chroma 初始化失败/超时后，本进程内不再重试（避免每次启动都等超时）
_chroma_unavailable = False


def _reset_chroma_state() -> None:
    """供测试使用。"""
    global _chroma_unavailable
    _chroma_unavailable = False
