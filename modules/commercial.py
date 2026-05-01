from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from urllib.parse import urlencode

DEFAULT_PRICE = "19,90"


def _secret(st, name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.getenv(name, default)


def get_config(st):
    return {
        "price": _secret(st, "DECIFRA_PRICE", DEFAULT_PRICE),
        "pix_key": _secret(st, "DECIFRA_PIX_KEY", ""),
        "whatsapp": _secret(st, "DECIFRA_WHATSAPP", ""),
        "unlock_secret": _secret(st, "DECIFRA_UNLOCK_SECRET", "troque-essa-chave-no-streamlit-secrets"),
        "checkout_url": _secret(st, "DECIFRA_CHECKOUT_URL", ""),
        "app_url": _secret(st, "DECIFRA_APP_URL", ""),
        "notification_url": _secret(st, "DECIFRA_NOTIFICATION_URL", ""),
        "mp_access_token": _secret(st, "MERCADO_PAGO_ACCESS_TOKEN", ""),
    }


def make_order_id(file_name: str = "analise") -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", file_name or "analise")[:32]
    base = f"{safe}-{time.time()}".encode("utf-8")
    return "DEC-" + hashlib.sha1(base).hexdigest()[:10].upper()


def make_unlock_code(order_id: str, secret: str) -> str:
    order_id = (order_id or "").strip().upper()
    sig = hmac.new((secret or "").encode("utf-8"), order_id.encode("utf-8"), hashlib.sha256).hexdigest()[:8].upper()
    return f"{order_id}-{sig}"


def validate_unlock_code(code: str, secret: str) -> bool:
    code = (code or "").strip().upper()
    match = re.match(r"^(DEC-[A-F0-9]{10})-([A-F0-9]{8})$", code)
    if not match:
        return False
    expected = make_unlock_code(match.group(1), secret)
    return hmac.compare_digest(expected, code)


def premium_active(st, cfg) -> bool:
    return bool(st.session_state.get("premium_unlocked")) or validate_unlock_code(
        st.session_state.get("unlock_code", ""),
        cfg.get("unlock_secret", ""),
    )


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def create_mp_preference(cfg: dict, order_id: str, title: str, amount: float) -> dict:
    token = cfg.get("mp_access_token", "").strip()
    if not token:
        return {"error": "Access Token do Mercado Pago não configurado."}

    try:
        import requests
    except Exception:
        return {"error": "A dependência `requests` não está instalada. Rode: pip install requests"}

    app_url = (cfg.get("app_url") or "").strip().rstrip("/")
    back_urls = {}
    if app_url.startswith("https://"):
        back_urls = {
            "success": f"{app_url}/?order_id={order_id}",
            "pending": f"{app_url}/?order_id={order_id}",
            "failure": f"{app_url}/?order_id={order_id}",
        }

    payload = {
        "items": [{
            "id": "decifra-analise-completa",
            "title": title,
            "description": "Liberação da análise completa DECIFRA Licitações",
            "quantity": 1,
            "currency_id": "BRL",
            "unit_price": float(amount),
        }],
        "external_reference": order_id,
        "statement_descriptor": "DECIFRA",
        "metadata": {"order_id": order_id, "product": "decifra_licitacoes"},
        "payment_methods": {"installments": 1},
    }

    if back_urls:
        payload["back_urls"] = back_urls
        payload["auto_return"] = "approved"

    notification_url = (cfg.get("notification_url") or "").strip()
    if notification_url.startswith("https://"):
        payload["notification_url"] = notification_url

    try:
        response = requests.post(
            "https://api.mercadopago.com/checkout/preferences",
            json=payload,
            headers=_headers(token),
            timeout=20,
        )
        data = response.json() if response.content else {}
        if response.status_code >= 400:
            msg = data.get("message") or data.get("error") or response.text
            return {"error": f"Mercado Pago recusou a preferência: {msg}"}

        return {
            "id": data.get("id", ""),
            "init_point": data.get("init_point") or data.get("sandbox_init_point") or "",
            "sandbox_init_point": data.get("sandbox_init_point", ""),
            "external_reference": order_id,
        }
    except Exception as exc:
        return {"error": f"Falha ao criar pagamento: {exc}"}


def get_mp_payment_status(cfg: dict, payment_id: str) -> dict:
    token = cfg.get("mp_access_token", "").strip()
    payment_id = str(payment_id or "").strip()
    if not token:
        return {"error": "Access Token do Mercado Pago não configurado."}
    if not payment_id:
        return {"error": "payment_id não informado no retorno."}

    try:
        import requests
    except Exception:
        return {"error": "A dependência `requests` não está instalada. Rode: pip install requests"}

    try:
        response = requests.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers=_headers(token),
            timeout=20,
        )
        data = response.json() if response.content else {}
        if response.status_code >= 400:
            msg = data.get("message") or data.get("error") or response.text
            return {"error": f"Não foi possível confirmar o pagamento: {msg}"}

        return {
            "id": str(data.get("id", "")),
            "status": data.get("status", ""),
            "status_detail": data.get("status_detail", ""),
            "external_reference": data.get("external_reference", ""),
            "transaction_amount": data.get("transaction_amount", 0),
        }
    except Exception as exc:
        return {"error": f"Falha ao consultar pagamento: {exc}"}
