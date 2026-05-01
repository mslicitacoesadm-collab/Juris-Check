from __future__ import annotations
import hashlib, hmac, time, re


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
        'unlock_secret': str(_secret_get(st, 'DECIFRA_UNLOCK_SECRET', 'troque-esta-chave')),
        'app_url': str(_secret_get(st, 'DECIFRA_APP_URL', '')),
        'notification_url': str(_secret_get(st, 'DECIFRA_NOTIFICATION_URL', '')),
        'mp_access_token': str(_secret_get(st, 'MERCADO_PAGO_ACCESS_TOKEN', '')),
    }


def make_order_id(file_name='analise'):
    slug = re.sub(r'[^A-Za-z0-9]+','-',file_name or 'analise').strip('-')[:18]
    return f'DEC-{int(time.time())}-{slug or "analise"}'


def make_unlock_code(order_id: str, secret: str):
    msg = (order_id or '').encode()
    key = (secret or 'secret').encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:10].upper()


def validate_unlock_code(code: str, secret: str, order_id: str = ''):
    code = (code or '').strip().upper()
    if not code: return False
    if order_id:
        return hmac.compare_digest(code, make_unlock_code(order_id, secret))
    # modo operador: aceita qualquer código de 10 caracteres gerado pelo painel do pedido
    return bool(re.fullmatch(r'[A-F0-9]{10}', code))


def premium_active(st, cfg):
    if st.session_state.get('premium_unlocked'):
        return True
    code = (st.session_state.get('unlock_code') or '').strip().upper()
    oid = st.session_state.get('order_id') or ''
    if oid and validate_unlock_code(code, cfg.get('unlock_secret',''), oid):
        st.session_state.premium_unlocked = True
        return True
    return False


def _amount(v):
    try: return float(str(v).replace('R$','').replace('.','').replace(',','.').strip())
    except Exception: return 19.90


def create_mp_preference(cfg, order_id: str, title: str, amount: float):
    token = cfg.get('mp_access_token') or ''
    if not token:
        return {'error':'Access Token do Mercado Pago não configurado.'}
    try:
        import requests
        app_url = (cfg.get('app_url') or '').rstrip('/')
        payload = {
            'items': [{'title': title, 'quantity': 1, 'currency_id': 'BRL', 'unit_price': float(amount)}],
            'external_reference': order_id,
            'auto_return': 'approved',
        }
        if app_url:
            payload['back_urls'] = {'success': app_url, 'failure': app_url, 'pending': app_url}
        if cfg.get('notification_url'):
            payload['notification_url'] = cfg['notification_url']
        r = requests.post('https://api.mercadopago.com/checkout/preferences', json=payload, headers={'Authorization': f'Bearer {token}'}, timeout=20)
        if r.status_code >= 300:
            return {'error': f'Mercado Pago retornou erro {r.status_code}: {r.text[:220]}'}
        data = r.json()
        return {'id': data.get('id'), 'init_point': data.get('init_point'), 'sandbox_init_point': data.get('sandbox_init_point')}
    except Exception as e:
        return {'error': f'Falha ao criar pagamento: {e}'}


def get_mp_payment_status(cfg, payment_id: str):
    token = cfg.get('mp_access_token') or ''
    if not token: return {'error':'Access Token do Mercado Pago não configurado.'}
    try:
        import requests
        r = requests.get(f'https://api.mercadopago.com/v1/payments/{payment_id}', headers={'Authorization': f'Bearer {token}'}, timeout=15)
        if r.status_code >= 300:
            return {'error': f'Não foi possível consultar pagamento ({r.status_code}).'}
        data = r.json()
        return {'status': data.get('status'), 'external_reference': data.get('external_reference'), 'raw': data}
    except Exception as e:
        return {'error': f'Falha ao consultar pagamento: {e}'}
