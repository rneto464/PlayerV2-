"""
API handler para Vercel Serverless Functions
Handler WSGI para Flask na Vercel
"""
import sys
import os

# Adiciona o diretório raiz ao path
root_dir = os.path.join(os.path.dirname(__file__), '..')
root_dir = os.path.abspath(root_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Muda para o diretório raiz
os.chdir(root_dir)

# Importa o app Flask
try:
    from app.server import app as flask_app
except Exception as e:
    print(f"Erro ao importar app Flask: {e}")
    import traceback
    traceback.print_exc()
    raise

# A Vercel espera que exportemos o app Flask diretamente
# O objeto Flask é WSGI-compatible e será usado pela Vercel
# Exportamos como 'app' para que a Vercel detecte automaticamente
app = flask_app
