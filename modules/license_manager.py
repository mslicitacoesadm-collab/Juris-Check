from __future__ import annotations

import os
import sqlite3
import secrets
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(exist_ok=True)
DB_PATH = RUNTIME_DIR / "juriscan_tokens.sqlite3"

TOKEN_ALPHABET = string.ascii_uppercase + string.digits


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS access_tokens (
            token TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            source TEXT DEFAULT 'manual',
            payment_ref TEXT,
            amount REAL DEFAULT 29.90,
            notes TEXT
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


def create_token(hours_valid: int = 24, source: str = "manual", payment_ref: str = "", amount: float = 29.90, notes: str = "") -> str:
    expires = datetime.now(timezone.utc) + timedelta(hours=hours_valid)
    token = "JS-" + "-".join("".join(secrets.choice(TOKEN_ALPHABET) for _ in range(4)) for _ in range(3))
    with _conn() as conn:
        conn.execute(
            "INSERT INTO access_tokens(token, created_at, expires_at, source, payment_ref, amount, notes) VALUES(?,?,?,?,?,?,?)",
            (token, now_iso(), expires.isoformat(), source, payment_ref, amount, notes),
        )
        conn.execute("INSERT INTO audit_log(created_at,event,details) VALUES(?,?,?)", (now_iso(), "token_created", token))
        conn.commit()
    return token


def validate_token(token: str, mark_used: bool = False) -> Dict[str, object]:
    token = (token or "").strip().upper()
    if not token:
        return {"ok": False, "reason": "Informe o código de liberação."}
    with _conn() as conn:
        row = conn.execute("SELECT * FROM access_tokens WHERE token=?", (token,)).fetchone()
        if not row:
            return {"ok": False, "reason": "Código não encontrado."}
        expires = datetime.fromisoformat(row["expires_at"])
        if expires < datetime.now(timezone.utc):
            return {"ok": False, "reason": "Código expirado."}
        if mark_used and not row["used_at"]:
            conn.execute("UPDATE access_tokens SET used_at=? WHERE token=?", (now_iso(), token))
            conn.execute("INSERT INTO audit_log(created_at,event,details) VALUES(?,?,?)", (now_iso(), "token_used", token))
            conn.commit()
        return {"ok": True, "token": token, "expires_at": row["expires_at"], "source": row["source"]}


def stats() -> Dict[str, object]:
    with _conn() as conn:
        total = conn.execute("SELECT COUNT(*) n FROM access_tokens").fetchone()["n"]
        used = conn.execute("SELECT COUNT(*) n FROM access_tokens WHERE used_at IS NOT NULL").fetchone()["n"]
        revenue = conn.execute("SELECT COALESCE(SUM(amount),0) v FROM access_tokens WHERE source IN ('mercado_pago','manual_pago','admin')").fetchone()["v"]
        last = conn.execute("SELECT token,created_at,expires_at,used_at,source,amount FROM access_tokens ORDER BY created_at DESC LIMIT 8").fetchall()
    return {"total_tokens": total, "used_tokens": used, "revenue": revenue, "last_tokens": [dict(x) for x in last]}


def log_event(event: str, details: str = "") -> None:
    with _conn() as conn:
        conn.execute("INSERT INTO audit_log(created_at,event,details) VALUES(?,?,?)", (now_iso(), event, details[:500]))
        conn.commit()


def get_payment_url() -> str:
    # Configure em .streamlit/secrets.toml ou variável de ambiente.
    return os.getenv("JURISCAN_PAYMENT_URL", "").strip()
