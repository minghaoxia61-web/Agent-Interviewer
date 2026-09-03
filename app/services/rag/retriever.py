"""大厂面经知识库检索（RAG 的 Phase 1 轻量实现）。

当前用字符 n-gram Jaccard + 关键词加权的纯 Python 检索，零重依赖；
Phase 2 升级路径：保持 Retriever 接口不变，底层换 ChromaDB 向量检索。
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    id: str
    company: str = "通用"
    category: str = "综合"
    question: str
    keywords: List[str] = Field(default_factory=list)


class Retriever:
    """检索接口：search(query, top_k, exclude) -> List[KnowledgeEntry]"""

    def __init__(self, knowledge_dir: Path) -> None:
        self.entries: List[KnowledgeEntry] = []
        if knowledge_dir.exists():
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
                        self.entries.append(KnowledgeEntry(**item))
                    except Exception:  # noqa: BLE001 - 单条脏数据不阻塞启动
                        continue

    @staticmethod
    def _grams(s: str) -> Set[str]:
        s = re.sub(r"\s+", " ", s.lower())
        grams: Set[str] = set()
        for run in re.findall(r"[\u4e00-\u9fff]+", s):
            if len(run) == 1:
                grams.add(run)
            else:
                grams.update(run[i : i + 2] for i in range(len(run) - 1))
        grams.update(re.findall(r"[a-z0-9]+", s))
        return grams

    def search(self, query: str, top_k: int = 1,
               exclude: Optional[List[str]] = None) -> List[KnowledgeEntry]:
        exclude = exclude or []
        q_grams = self._grams(query)
        scored: List[Any] = []
        for e in self.entries:
            if e.id in exclude:
                continue
            score = 0.0
            for kw in e.keywords:
                if kw.lower() in query.lower():
                    score += 3.0
            t_grams = self._grams(e.question + " " + " ".join(e.keywords))
            union = len(q_grams | t_grams)
            if union:
                score += 4.0 * len(q_grams & t_grams) / union
            scored.append((score, e))
        scored.sort(key=lambda x: (-x[0], x[1].id))
        return [e for _, e in scored[:top_k]]

    def pick(self, query: str, exclude: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """返回单条命中的题目 dict；知识库为空或全部命中排除项时返回 None。"""
        hits = self.search(query, top_k=1, exclude=exclude)
        return hits[0].model_dump() if hits else None
