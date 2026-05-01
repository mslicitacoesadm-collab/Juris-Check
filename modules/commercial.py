from __future__ import annotations
import os, hashlib, hmac, time, re
from typing import Any, Dict, Tuple

DEFAULT_PRICE='19,90'

def _secret(st, name, default=''):
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.getenv(name, default)

def get_config(st):
    return {
        'price': _secret(st, 'DECIFRA_PRICE', DEFAULT_PRICE),
        'pix_key': _secret(st, 'DECIFRA_PIX_KEY', ''),
        'whatsapp': re.sub(r'\D+', '', _secret(st, 'DECIFRA_WHATSAPP', '')),
        'unlock_secret': _secret(st, 'DECIFRA_UNLOCK_SECRET', 'troque-essa-chave-no-streamlit-secrets'),
        'checkout_url': _secret(st, 'DECIFRA_CHECKOUT_URL', ''),
        'mp_access_token': _secret(st, 'MERCADO_PAGO_ACCESS_TOKEN', ''),
        'app_url': _secret(st, 'DECIFRA_APP_URL', ''),
        'notification_url': _secret(st, 'DECIFRA_NOTIFICATION_URL', ''),
        'currency_id': _secret(st, 'DECIFRA_CURRENCY_ID', 'BRL'),
    }

def price_to_float(price: str) -> float:
    s = str(price or DEFAULT_PRICE).replace('R$', '').strip().replace('.', '').replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 19.90

def make_order_id(file_name='analise'):
    base=f'{file_name}-{time.time()}'.encode()
    return 'DEC-' + hashlib.sha1(base).hexdigest()[:10].upper()

def make_unlock_code(order_id, secret):
    sig=hmac.new(secret.encode(), order_id.encode(), hashlib.sha256).hexdigest()[:8].upper()
    return f'{order_id}-{sig}'

def validate_unlock_code(code, secret):
    code=(code or '').strip().upper()
    m=re.match(r'^(DEC-[A-F0-9]{10})-([A-F0-9]{8})$', code)
    if not m: return False
    return hmac.compare_digest(make_unlock_code(m.group(1), secret), code)

def premium_active(st, cfg):
    return bool(st.session_state.get('premium_unlocked')) or validate_unlock_code(st.session_state.get('unlock_code',''), cfg['unlock_secret'])

def create_mp_preference(cfg: Dict[str, str], order_id: str, title: str='DECIFRA Licitações - Análise Premium') -> Tuple[bool, Dict[str, Any]]:
    token = cfg.get('mp_access_token','').strip()
    if not token:
        return False, {'error': 'MERCADO_PAGO_ACCESS_TOKEN não configurado.'}
    try:
        import mercadopago
        sdk = mercadopago.SDK(token)
        app_url = (cfg.get('app_url') or '').rstrip('/')
        preference = {
            'items': [{
                'title': title,
                'description': 'Liberação da análise completa com exportação premium.',
                'quantity': 1,
                'currency_id': cfg.get('currency_id', 'BRL'),
                'unit_price': price_to_float(cfg.get('price')),
            }],
            'external_reference': order_id,
            'statement_descriptor': 'DECIFRA',
            'auto_return': 'approved',
            'metadata': {'order_id': order_id, 'product': 'decifra_licitacoes'},
        }
        if app_url.startswith('https://'):
            preference['back_urls'] = {
                'success': f'{app_url}?decifra_order={order_id}',
                'pending': f'{app_url}?decifra_order={order_id}&pending=1',
                'failure': f'{app_url}?decifra_order={order_id}&failure=1',
            }
        notification_url = (cfg.get('notification_url') or '').strip()
        if notification_url.startswith('https://'):
            preference['notification_url'] = notification_url
        response = sdk.preference().create(preference)
        body = response.get('response', {}) if isinstance(response, dict) else {}
        if body.get('init_point') or body.get('sandbox_init_point'):
            return True, body
        return False, {'error': body or response}
    except Exception as e:
        return False, {'error': str(e)}

def verify_mp_payment(cfg: Dict[str, str], payment_id: str, expected_order_id: str='') -> Tuple[bool, Dict[str, Any]]:
    token = cfg.get('mp_access_token','').strip()
    if not token or not payment_id:
        return False, {'error': 'Token ou payment_id ausente.'}
    try:
        import mercadopago
        sdk = mercadopago.SDK(token)
        response = sdk.payment().get(payment_id)
        body = response.get('response', {}) if isinstance(response, dict) else {}
        approved = body.get('status') == 'approved'
        same_order = True
        if expected_order_id:
            same_order = body.get('external_reference') in ('', None, expected_order_id)
        return bool(approved and same_order), body
    except Exception as e:
        return False, {'error': str(e)}
