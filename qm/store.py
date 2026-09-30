"""Tables + vector store.

Numbers come from the CSV/SQLite tables. The vector store only holds TEXT (job descriptions, RFQ
emails, debriefs, NCRs, override notes) and is used for description similarity (Locked Decision 5).

Vector backend: Chroma (persistent, cosine space, default local MiniLM embedding) with a TF-IDF
fallback if Chroma or its embedding model is unavailable (e.g. offline first run). Force the
fallback with QM_EMBEDDINGS=tfidf.
"""
from __future__ import annotations

import logging
import os
import threading
from functools import lru_cache

import numpy as np
import pandas as pd

from qm import config

log = logging.getLogger("qm.store")
_LOCK = threading.RLock()

TABLES = ["customers", "jobs", "bom_lines", "routing_ops", "docs", "material_prices", "work_centers"]
DATE_COLS = {"jobs": ["quote_date"], "bom_lines": ["cost_date"], "docs": ["date"], "material_prices": ["quote_date"]}
MEMORY_FILE = "overrides.csv"


# ---------------------------------------------------------------- tables
def ensure_data() -> None:
    if not (config.DATA_DIR / "jobs.csv").exists():
        from qm import data_gen
        data_gen.save(data_gen.generate())


@lru_cache(maxsize=1)
def base_tables() -> dict[str, pd.DataFrame]:
    ensure_data()
    out = {}
    for name in TABLES:
        df = pd.read_csv(config.DATA_DIR / f"{name}.csv")
        for c in DATE_COLS.get(name, []):
            df[c] = pd.to_datetime(df[c]).dt.date
        out[name] = df
    j = out["jobs"]
    for c in ["cosmetic_weld", "first_run", "has_fixture_line", "won"]:
        j[c] = j[c].astype(bool)
    j["finish"] = j["finish"].fillna("")
    d = out["docs"]
    for c in ["work_center", "line_key"]:
        d[c] = d[c].where(d[c].notna(), None)
    return out


def memory_docs() -> pd.DataFrame:
    f = config.MEMORY_DIR / MEMORY_FILE
    cols = list(base_tables()["docs"].columns)
    if not f.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(f)
    if df.empty:
        return pd.DataFrame(columns=cols)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for c in ["work_center", "line_key"]:
        df[c] = df[c].where(df[c].notna(), None)
    return df[cols + [c for c in df.columns if c not in cols]]


def tables() -> dict[str, pd.DataFrame]:
    """Base tables with the demo-session memory (override docs) appended to `docs`."""
    t = dict(base_tables())
    mem = memory_docs()
    if not mem.empty:
        t["docs"] = pd.concat([t["docs"], mem[t["docs"].columns.tolist()]], ignore_index=True)
    return t


def customers_by_name() -> dict[str, dict]:
    c = base_tables()["customers"]
    return {r["name"].lower(): r.to_dict() for _, r in c.iterrows()}


# ---------------------------------------------------------------- vector store
class _TfidfBackend:
    name = "tfidf"

    def __init__(self, corpus: list[str]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1).fit(corpus)

    def embed(self, texts: list[str]) -> np.ndarray:
        m = self.vec.transform(texts).toarray()
        n = np.linalg.norm(m, axis=1, keepdims=True)
        n[n == 0] = 1
        return m / n


class _ChromaBackend:
    name = "chroma-minilm"

    def __init__(self):
        import chromadb
        from chromadb.config import Settings
        from chromadb.utils import embedding_functions

        self.ef = embedding_functions.DefaultEmbeddingFunction()
        self.ef(["warm-up"])  # triggers the one-time local model download; raises if impossible
        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(config.CHROMA_DIR),
                                                settings=Settings(anonymized_telemetry=False))
        # Rebuild the collections if the base data changed since they were built.
        fp = _data_fingerprint()
        fp_file = config.CHROMA_DIR / "_fingerprint.txt"
        if not fp_file.exists() or fp_file.read_text() != fp:
            for c in ("jobs", "docs"):
                try:
                    self.client.delete_collection(c)
                except Exception:
                    pass
            fp_file.write_text(fp)

    def embed(self, texts: list[str]) -> np.ndarray:
        m = np.array(self.ef(texts), dtype=float)
        n = np.linalg.norm(m, axis=1, keepdims=True)
        n[n == 0] = 1
        return m / n

    def collection(self, name: str):
        return self.client.get_or_create_collection(name, embedding_function=self.ef,
                                                    metadata={"hnsw:space": "cosine"})


class VectorStore:
    """Holds normalized embeddings for jobs + docs in memory (backed by Chroma on disk)."""

    def __init__(self):
        t = base_tables()
        self.backend = None
        if os.getenv("QM_EMBEDDINGS", "").lower() != "tfidf":
            try:
                self.backend = _ChromaBackend()
            except Exception as e:  # no chromadb / no model download possible -> TF-IDF
                log.warning("Chroma embeddings unavailable (%s); using TF-IDF", type(e).__name__)
        if self.backend is None:
            corpus = list(t["jobs"].description) + list(t["docs"].text)
            self.backend = _TfidfBackend(corpus)
        self.vecs: dict[str, np.ndarray] = {}
        self._qcache: dict[str, np.ndarray] = {}
        self._ingest("jobs", t["jobs"].job_id.tolist(), job_texts(t["jobs"]),
                     [{"part_family": f} for f in t["jobs"].part_family])
        d = t["docs"]
        self._ingest("docs", d.doc_id.tolist(), d.text.tolist(),
                     [{"doc_type": a, "part_family": b} for a, b in zip(d.doc_type, d.part_family)])
        self.sync_memory()

    def _ingest(self, cname: str, ids: list[str], texts: list[str], metas: list[dict]) -> None:
        if isinstance(self.backend, _ChromaBackend):
            col = self.backend.collection(cname)
            have = set(col.get(ids=ids, include=[])["ids"]) if ids else set()
            todo = [i for i, x in enumerate(ids) if x not in have]
            for s in range(0, len(todo), 256):
                chunk = todo[s:s + 256]
                col.add(ids=[ids[i] for i in chunk], documents=[texts[i] for i in chunk],
                        metadatas=[metas[i] for i in chunk])
            got = col.get(ids=ids, include=["embeddings"])
            for i, e in zip(got["ids"], got["embeddings"]):
                v = np.array(e, dtype=float)
                self.vecs[i] = v / (np.linalg.norm(v) or 1)
        else:
            for i, v in zip(ids, self.backend.embed(texts)):
                self.vecs[i] = v

    def sync_memory(self) -> None:
        """Make the vector store match data/memory (adds new override docs, drops removed ones)."""
        with _LOCK:
            mem = memory_docs()
            want = set(mem.doc_id) if not mem.empty else set()
            stale = [k for k in self.vecs if k.startswith("M-") and k not in want]
            if stale and isinstance(self.backend, _ChromaBackend):
                self.backend.collection("docs").delete(ids=stale)
            for k in stale:
                self.vecs.pop(k, None)
            new = mem[~mem.doc_id.isin(list(self.vecs))] if not mem.empty else mem
            if not new.empty:
                self._ingest("docs", new.doc_id.tolist(), new.text.tolist(),
                             [{"doc_type": "override", "part_family": str(f)} for f in new.part_family])

    def embed_query(self, text: str) -> np.ndarray:
        if text not in self._qcache:
            self._qcache[text] = self.backend.embed([text])[0]
        return self._qcache[text]

    def cos(self, text: str, ids: list[str]) -> dict[str, float]:
        q = self.embed_query(text)
        return {i: float(np.clip(self.vecs[i] @ q, 0, 1)) if i in self.vecs else 0.0 for i in ids}


def _data_fingerprint() -> str:
    import hashlib
    h = hashlib.sha256()
    for name in ("jobs", "docs"):
        h.update((config.DATA_DIR / f"{name}.csv").read_bytes())
    return h.hexdigest()[:16]


def job_texts(jobs: pd.DataFrame) -> list[str]:
    return [f"{pn}: {d}" for pn, d in zip(jobs.part_number, jobs.description)]


_STORE: VectorStore | None = None


def vector_store() -> VectorStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = VectorStore()
        return _STORE


def reset_vector_cache() -> None:
    global _STORE
    with _LOCK:
        _STORE = None
