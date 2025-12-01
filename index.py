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

# A Vercel com @vercel/python espera que o app Flask seja acessível
# O app já está importado e será usado automaticamente pela Vercel

