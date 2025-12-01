"""
Ponto de entrada para a Vercel Serverless Function
Flask app entry point for Vercel
"""
import sys
import os

# Adiciona o diretório atual ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Importa o app Flask
try:
    from app.server import app
except ImportError as e:
    print(f"Erro ao importar app: {e}")
    raise

# A Vercel detecta automaticamente o objeto 'app' Flask quando o arquivo se chama app.py
# O objeto Flask app é WSGI-compatible e será usado diretamente pela Vercel

