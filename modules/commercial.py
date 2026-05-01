from __future__ import annotations
import os, hashlib, hmac, time, re

DEFAULT_PRICE='19,90'

def get_config(st):
    def secret(name, default=''):
        try: return str(st.secrets.get(name, default))
        except Exception: return os.getenv(name, default)
    return {
        'price': secret('DECIFRA_PRICE', DEFAULT_PRICE),
        'pix_key': secret('DECIFRA_PIX_KEY', ''),
        'whatsapp': secret('DECIFRA_WHATSAPP', ''),
        'unlock_secret': secret('DECIFRA_UNLOCK_SECRET', 'troque-essa-chave-no-streamlit-secrets'),
        'checkout_url': secret('DECIFRA_CHECKOUT_URL', ''),
    }

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
