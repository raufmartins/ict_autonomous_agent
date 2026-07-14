"""
RAG Store — ChromaDB local vector database for high-probability WIN trade context.
Persists embeddings of every WIN trade so the Gemini auditor can reference
the 3 most structurally similar past setups before approving a new signal.
"""
import os
import logging

import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger("ict_trader")

_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "rag_db")
_COLLECTION = "win_trades"
_EF = embedding_functions.DefaultEmbeddingFunction()  # all-MiniLM-L6-v2, local


def _collection():
    client = chromadb.PersistentClient(path=_DB_PATH)
    return client.get_or_create_collection(
        name=_COLLECTION,
        embedding_function=_EF,
        metadata={"hnsw:space": "cosine"},
    )


def _trade_to_text(trade: dict) -> str:
    fvg_size = round(
        float(trade.get("fvg_top", 0) or 0) - float(trade.get("fvg_bottom", 0) or 0), 4
    )
    return (
        f"asset={trade.get('asset', '')} "
        f"action={trade.get('action', '')} "
        f"zone={trade.get('zone_hit', trade.get('zone', ''))} "
        f"session={trade.get('session', '')} "
        f"fvg_size={fvg_size} "
        f"r={trade.get('r', '')} "
        f"justification={trade.get('justification', '')}"
    )


def save_win_trade(trade: dict) -> None:
    """Embed and persist a WIN trade. Called automatically by close_trade()."""
    try:
        col = _collection()
        doc_id = (
            f"{trade.get('asset','')}_{trade.get('time','').replace(':','')}_{trade.get('action','')}"
        )
        col.upsert(
            documents=[_trade_to_text(trade)],
            metadatas=[{k: str(v) for k, v in trade.items()}],
            ids=[doc_id],
        )
        logger.info("RAG: trade WIN salvo | %s %s", trade.get("asset"), trade.get("action"))
    except Exception as e:
        logger.warning("RAG save error: %s", e)


def query_similar_wins(payload: dict, n: int = 3) -> list[dict]:
    """Return the n most similar past WIN trades to the current signal payload."""
    try:
        col = _collection()
        total = col.count()
        if total == 0:
            return []
        query_text = _trade_to_text(payload)
        results = col.query(
            query_texts=[query_text],
            n_results=min(n, total),
        )
        return results.get("metadatas", [[]])[0]
    except Exception as e:
        logger.warning("RAG query error: %s", e)
        return []
