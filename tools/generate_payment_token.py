"""Gera um token JuriScan manualmente.
Uso: python tools/generate_payment_token.py
"""
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from modules.license_manager import create_token

if __name__ == "__main__":
    print(create_token(hours_valid=24, source="manual_pago", amount=29.90, notes="gerado por script"))
