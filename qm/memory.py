"""S9 Memory write-back: every human override (Gate 1 edit or line removal, Gate 2 out-of-range price)
becomes a `docs` row (doc_type=override) written to CSV + SQLite + the vector store immediately.
Line-level routing overrides come back as evidence on the next similar RFQ; other decisions are shown
as context (e.g. past pricing decisions on similar quotes).

Demo-session memory lives in data/memory/overrides.csv (gitignored). Reset deletes it.
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from qm import config, store
from qm.data_gen import frac

COLUMNS = ["doc_id", "job_id", "doc_type", "date", "part_family", "work_center", "line_key", "old_value",
           "new_value", "text", "kind", "rfq_id"]


def _file():
    config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return config.MEMORY_DIR / store.MEMORY_FILE


def list_memory() -> pd.DataFrame:
    return store.memory_docs()


def _next_id(mem: pd.DataFrame) -> str:
    n = 1 + max([int(str(i)[2:]) for i in mem.doc_id] or [0]) if not mem.empty else 1
    return f"M-{n:04d}"


def _describe(spec: dict) -> str:
    bits = [(spec.get("part_family") or "part").replace("_", " ")]
    if spec.get("part_number"):
        bits.append(spec["part_number"])
    if spec.get("material"):
        t = spec.get("thickness_in")
        bits.append(f"{spec['material']} {frac(float(t)) + chr(34) if t else ''}".strip())
    if spec.get("cosmetic_weld") is not None:
        bits.append("cosmetic weld" if spec["cosmetic_weld"] else "standard weld")
    if spec.get("first_run"):
        bits.append("first run")
    return ", ".join(bits)


def _write(row: dict) -> dict:
    mem = list_memory()
    row = {c: row.get(c) for c in COLUMNS}
    row["doc_id"] = _next_id(mem)
    df = pd.concat([mem[COLUMNS] if not mem.empty else pd.DataFrame(columns=COLUMNS), pd.DataFrame([row])],
                   ignore_index=True)
    df.to_csv(_file(), index=False)
    try:  # mirror into SQLite (the shop's system of record in a real install)
        with sqlite3.connect(config.SQLITE_PATH) as con:
            pd.DataFrame([row])[COLUMNS[:10]].to_sql("docs", con, if_exists="append", index=False)
    except Exception:
        pass
    store.vector_store().sync_memory()
    return row


def record_line_override(rfq_id: str, spec: dict, line_key: str, label: str, work_center: str | None,
                         old: float, new: float, reason: str) -> dict:
    text = (f"Estimator override on {label} ({_describe(spec)}): {old:.2f}→{new:.2f}. "
            f"Reason: {reason.strip()}")
    return _write(dict(job_id=rfq_id, doc_type="override", date=config.AS_OF, part_family=spec.get("part_family"),
                       work_center=work_center, line_key=line_key, old_value=float(old), new_value=float(new),
                       text=text, kind="gate1_line", rfq_id=rfq_id))


def record_decision(rfq_id: str, spec: dict, kind: str, text: str) -> dict:
    """Non-line decisions: Gate 2 price outside the range, reasoned ask/assume flips."""
    full = f"{text.strip()} ({_describe(spec)})"
    return _write(dict(job_id=rfq_id, doc_type="override", date=config.AS_OF, part_family=spec.get("part_family"),
                       work_center=None, line_key=None, old_value=None, new_value=None, text=full, kind=kind,
                       rfq_id=rfq_id))


def remove_for_rfq(rfq_id: str, kinds: tuple[str, ...] = ("gate1_line",)) -> int:
    """Drop this RFQ's earlier memory rows of the given kinds (re-approving Gate 1 replaces them)."""
    mem = list_memory()
    if mem.empty or "rfq_id" not in mem.columns:
        return 0
    keep = mem[~((mem.rfq_id == rfq_id) & mem.kind.isin(kinds))]
    n = len(mem) - len(keep)
    if n:
        keep[COLUMNS].to_csv(_file(), index=False)
        store.vector_store().sync_memory()
    return n


def reset_memory() -> int:
    """Remove every demo-session override (CSV, SQLite, vector store)."""
    mem = list_memory()
    n = len(mem)
    f = config.MEMORY_DIR / store.MEMORY_FILE
    if f.exists():
        f.unlink()
    try:
        with sqlite3.connect(config.SQLITE_PATH) as con:
            con.execute("DELETE FROM docs WHERE doc_id LIKE 'M-%'")
    except Exception:
        pass
    store.vector_store().sync_memory()
    return n
