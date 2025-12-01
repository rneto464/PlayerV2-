"""
Ponto de entrada para a Vercel Serverless Function
"""
import sys
import os

# Adiciona o diretório raiz ao path
root_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, root_dir)

# Muda para o diretório raiz para garantir que os caminhos relativos funcionem
os.chdir(root_dir)

from app.server import app

# Exporta o app para a Vercel
# A Vercel espera que o handler seja o objeto Flask app
handler = app

