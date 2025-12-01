"""
Ponto de entrada para a Vercel Serverless Function
"""
import sys
import os

# Adiciona o diretório atual ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Importa o app Flask
from app.server import app

# A Vercel espera que o app Flask seja exportado como 'handler'
# ou que seja acessível diretamente como 'app'
# Exportamos ambos para garantir compatibilidade
handler = app

