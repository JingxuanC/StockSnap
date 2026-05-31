"""RAG 知识库 - ChromaDB 向量存储 + 混合检索
存储: 历史分析报告/公司数据/行业知识
检索: 语义相似度 + 关键词匹配 + 时间衰减
"""
from __future__ import annotations
import json, time, logging, hashlib
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    _chroma_client = chromadb.Client(ChromaSettings(anonymized_telemetry=False))
    _collection = _chroma_client.get_or_create_collection(
        name="stocksnap_knowledge",
        metadata={"hnsw:space": "cosine"}
    )
    HAS_CHROMADB = True
    logger.info("ChromaDB 知识库已就绪")
except ImportError:
    _chroma_client = None; _collection = None; HAS_CHROMADB = False
    logger.warning("ChromaDB 未安装，RAG已禁用 (pip install chromadb)")

def _hash_text(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:16]

def add_knowledge(doc_id: str, text: str, metadata: dict = None):
    """向知识库添加文档"""
    if not HAS_CHROMADB: return
    try:
        meta = metadata or {}
        meta["timestamp"] = datetime.now(timezone.utc).isoformat()
        # 分批处理长文本 (每500字一块)
        chunks = [text[i:i+500] for i in range(0, len(text), 500)]
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        _collection.add(documents=chunks, ids=ids, metadatas=[meta]*len(chunks))
        logger.info(f"[RAG] 添加文档: {doc_id} ({len(chunks)}块)")
    except Exception as e:
        logger.error(f"[RAG] 添加失败: {e}")

def search(query: str, n_results: int = 5, recency_boost: bool = True) -> list[str]:
    """检索相关知识"""
    if not HAS_CHROMADB or _collection.count() == 0:
        return []
    try:
        results = _collection.query(query_texts=[query], n_results=n_results)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        # 时间衰减: 越新的文档权重越高
        if recency_boost and metas:
            scored = []
            now = time.time()
            for i, (doc, meta) in enumerate(zip(docs, metas)):
                ts = meta.get("timestamp", "")
                age_days = 999
                if ts:
                    try:
                        age_seconds = now - datetime.fromisoformat(ts).timestamp()
                        age_days = max(0, age_seconds / 86400)
                    except: pass
                decay = 1.0 / (1.0 + age_days/7)  # 7天半衰
                scored.append((doc, decay))
            scored.sort(key=lambda x: x[1], reverse=True)
            return [s[0] for s in scored]
        return docs
    except Exception as e:
        logger.error(f"[RAG] 检索失败: {e}")
        return []

def store_analysis(symbol: str, market: str, analysis_json: dict, markdown: str):
    """存储分析报告到知识库"""
    doc_id = f"analysis:{market}:{symbol}:{int(time.time())}"
    company = analysis_json.get("company", {})
    rating = analysis_json.get("rating", {})
    add_knowledge(doc_id, markdown[:3000], {
        "type": "analysis", "symbol": symbol, "market": market,
        "name": company.get("name", symbol),
        "rating": rating.get("decision"), "confidence": rating.get("confidence"),
        "score": (analysis_json.get("scores") or {}).get("overall", 0),
    })

def search_relevant_analyses(symbol: str, market: str, query: str = "") -> list[str]:
    """检索相关的历史分析"""
    q = query or f"{symbol} 投资分析 估值 风险 催化剂"
    return search(q)

def get_knowledge_stats() -> dict:
    if not HAS_CHROMADB:
        return {"enabled": False, "documents": 0}
    return {"enabled": True, "documents": _collection.count()}
