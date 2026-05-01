from __future__ import annotations
import hashlib
import hmac
import json
import re
import time
from pathlib import Path


DEFAULT_ADMIN_PASSWORD = "Skcoqdra.4"


def _secret_get(st, key, default=''):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def get_config(st):
    return {
        'price': str(_secret_get(st, 'DECIFRA_PRICE', '19,90')),
        'pix_key': str(_secret_get(st, 'DECIFRA_PIX_KEY', '')),
        'whatsapp': str(_secret_get(st, 'DECIFRA_WHATSAPP', '')),
        'unlock_secret': str(_secret_get(st, 'DECIFRA_UNLOCK_SECRET', 'troque-esta-chave-em-producao')),
        'app_url': str(_secret_get(st, 'DECIFRA_APP_URL', '')),
        'notification_url': str(_secret_get(st, 'DECIFRA_NOTIFICATION_URL', '')),
        'mp_access_token': str(_secret_get(st, 'MERCADO_PAGO_ACCESS_TOKEN', '')),
        'admin_password': str(_secret_get(st, 'DECIFRA_ADMIN_PASSWORD', DEFAULT_ADMIN_PASSWORD)),
        'default_mode': str(_secret_get(st, 'DECIFRA_DEFAULT_MODE', 'pagamento')).lower(),
        'free_limit': int(_secret_get(st, 'DECIFRA_FREE_LIMIT', 1) or 1),
        'brand_name': str(_secret_get(st, 'DECIFRA_BRAND_NAME', 'DECIFRA Licitações')),
    }


def load_admin_settings(path: Path, cfg: dict) -> dict:
    defaults = {
        'mode': cfg.get('default_mode', 'pagamento') if cfg.get('default_mode') in {'pagamento', 'livre'} else 'pagamento',
        'price': cfg.get('price', '19,90'),
        'free_limit': int(cfg.get('free_limit', 1) or 1),
        'blur_preview': True,
        'mp_enabled': True,
        'pix_enabled': True,
        'manual_code_enabled': True,
        'show_manual_search': True,
        'show_admin_teaser': True,
        'whatsapp': cfg.get('whatsapp', ''),
        'pix_key': cfg.get('pix_key', ''),
    }
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            defaults.update({k: data[k] for k in defaults.keys() if k in data})
            defaults['free_limit'] = max(0, int(defaults.get('free_limit', 1)))
    except Exception:
        pass
    return defaults


def save_admin_settings(path: Path, settings: dict) -> None:
    safe = dict(settings)
    safe['mode'] = safe.get('mode') if safe.get('mode') in {'pagamento', 'livre'} else 'pagamento'
    safe['free_limit'] = max(0, int(safe.get('free_limit', 1) or 0))
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding='utf-8')


def price_to_float(price_text: str) -> float:
    try:
        value = str(price_text).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(value)
    except Exception:
        return 19.90


def make_order_id(file_name='analise'):
    slug = re.sub(r'[^A-Za-z0-9]+', '-', file_name or 'analise').strip('-')[:18]
    return f'DEC-{int(time.time())}-{slug or "analise"}'


def make_unlock_code(order_id: str, secret: str):
    msg = (order_id or '').encode()
    key = (secret or 'secret').encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:10].upper()


def validate_unlock_code(code: str, secret: str, order_id: str = ''):
    code = (code or '').strip().upper()
    if not code:
        return False
    if order_id:
        return hmac.compare_digest(code, make_unlock_code(order_id, secret))
    return bool(re.fullmatch(r'[A-F0-9]{10}', code))


def premium_active(st, cfg):
    if st.session_state.get('premium_unlocked'):
        return True
    code = (st.session_state.get('unlock_code') or '').strip().upper()
    order_id = st.session_state.get('order_id') or ''
    if order_id and validate_unlock_code(code, cfg.get('unlock_secret', ''), order_id):
        st.session_state.premium_unlocked = True
        return True
    return False


def create_mp_preference(cfg, settings: dict, order_id: str, title: str, amount: float):
    token = cfg.get('mp_access_token') or ''
    if not token:
        return {'error': 'Access Token do Mercado Pago não configurado.'}
    try:
        import requests
        app_url = (cfg.get('app_url') or '').rstrip('/')
        payload = {
            'items': [{
                'id': 'decifra-relatorio',
                'title': title,
                'quantity': 1,
                'currency_id': 'BRL',
                'unit_price': float(amount),
            }],
            'external_reference': order_id,
            'statement_descriptor': 'DECIFRA',
            'auto_return': 'approved',
        }
        if app_url:
            payload['back_urls'] = {'success': app_url, 'failure': app_url, 'pending': app_url}
        if cfg.get('notification_url'):
            payload['notification_url'] = cfg['notification_url']
        r = requests.post(
            'https://api.mercadopago.com/checkout/preferences',
            json=payload,
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            timeout=20,
        )
        if r.status_code >= 300:
            return {'error': f'Mercado Pago retornou erro {r.status_code}: {r.text[:260]}'}
        data = r.json()
        return {'id': data.get('id'), 'init_point': data.get('init_point'), 'sandbox_init_point': data.get('sandbox_init_point')}
    except Exception as e:
        return {'error': f'Falha ao criar pagamento: {e}'}


def get_mp_payment_status(cfg, payment_id: str):
    token = cfg.get('mp_access_token') or ''
    if not token:
        return {'error': 'Access Token do Mercado Pago não configurado.'}
    try:
        import requests
        r = requests.get(
            f'https://api.mercadopago.com/v1/payments/{payment_id}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=15,
        )
        if r.status_code >= 300:
            return {'error': f'Não foi possível consultar pagamento ({r.status_code}).'}
        data = r.json()
        return {'status': data.get('status'), 'external_reference': data.get('external_reference'), 'raw': data}
    except Exception as e:
        return {'error': f'Falha ao consultar pagamento: {e}'}
