from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(exist_ok=True)
DB_PATH = RUNTIME_DIR / "juriscan_growth.sqlite3"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            audit_id TEXT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            whatsapp TEXT NOT NULL,
            company TEXT,
            city_uf TEXT,
            interest TEXT,
            piece_type TEXT,
            file_name TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            event TEXT NOT NULL,
            details TEXT
        )
        """
    )
    conn.commit()
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_lead(lead: Dict[str, object]) -> Dict[str, object]:
    required = ["name", "email", "whatsapp"]
    missing = [field for field in required if not str(lead.get(field) or "").strip()]
    if missing:
        return {"ok": False, "reason": "Preencha nome, e-mail e WhatsApp para receber o relatório."}

    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO leads(created_at,audit_id,name,email,whatsapp,company,city_uf,interest,piece_type,file_name)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now_iso(),
                str(lead.get("audit_id") or "")[:60],
                str(lead.get("name") or "").strip()[:160],
                str(lead.get("email") or "").strip()[:180],
                str(lead.get("whatsapp") or "").strip()[:80],
                str(lead.get("company") or "").strip()[:180],
                str(lead.get("city_uf") or "").strip()[:120],
                str(lead.get("interest") or "").strip()[:80],
                str(lead.get("piece_type") or "").strip()[:120],
                str(lead.get("file_name") or "").strip()[:220],
            ),
        )
        conn.execute(
            "INSERT INTO audit_log(created_at,event,details) VALUES(?,?,?)",
            (now_iso(), "lead_captured", str(lead.get("email") or "")[:180]),
        )
        conn.commit()
    return {"ok": True}


def stats() -> Dict[str, object]:
    with _conn() as conn:
        total_leads = conn.execute("SELECT COUNT(*) n FROM leads").fetchone()["n"]
        companies = conn.execute("SELECT COUNT(DISTINCT NULLIF(TRIM(company),'')) n FROM leads").fetchone()["n"]
        analyses = conn.execute("SELECT COUNT(*) n FROM audit_log WHERE event='audit_created'").fetchone()["n"]
        by_state = conn.execute(
            "SELECT city_uf, COUNT(*) total FROM leads WHERE TRIM(COALESCE(city_uf,''))<>'' GROUP BY city_uf ORDER BY total DESC LIMIT 8"
        ).fetchall()
        by_interest = conn.execute(
            "SELECT interest, COUNT(*) total FROM leads WHERE TRIM(COALESCE(interest,''))<>'' GROUP BY interest ORDER BY total DESC LIMIT 8"
        ).fetchall()
        by_piece = conn.execute(
            "SELECT piece_type, COUNT(*) total FROM leads WHERE TRIM(COALESCE(piece_type,''))<>'' GROUP BY piece_type ORDER BY total DESC LIMIT 8"
        ).fetchall()
        last_leads = conn.execute(
            "SELECT created_at,name,email,whatsapp,company,city_uf,interest,piece_type,file_name FROM leads ORDER BY created_at DESC LIMIT 30"
        ).fetchall()
    return {
        "total_leads": total_leads,
        "companies": companies,
        "analyses": analyses,
        "by_state": [dict(x) for x in by_state],
        "by_interest": [dict(x) for x in by_interest],
        "by_piece": [dict(x) for x in by_piece],
        "last_leads": [dict(x) for x in last_leads],
    }


def log_event(event: str, details: str = "") -> None:
    with _conn() as conn:
        conn.execute("INSERT INTO audit_log(created_at,event,details) VALUES(?,?,?)", (now_iso(), event, details[:500]))
        conn.commit()
