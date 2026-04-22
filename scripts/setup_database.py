# Nome do ficheiro: scripts/setup_database.py
import os
import sqlite3
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError

# --- Configuração de Caminhos ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_DE_MUSICAS = os.path.join(ROOT_DIR, 'media', 'minhas_musicas')
DB_FILE = os.path.join(ROOT_DIR, 'data', 'banco_musicas.db')

def criar_tabelas(conn):
    """Cria TODAS as tabelas necessárias com a estrutura genérica para múltiplos serviços."""
    cursor = conn.cursor()
    print("A criar/verificar todas as tabelas...")

    # Tabela de utilizadores genérica
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_user_id TEXT NOT NULL,
            service_name TEXT NOT NULL,
            display_name TEXT,
            data_primeiro_login DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(service_user_id, service_name)
        )
    """)

    # Tabela de playlists salvas, agora com colunas genéricas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlists_salvas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nome_playlist TEXT NOT NULL,
            playlist_url TEXT, -- URL genérico para a playlist (Spotify ou YouTube)
            service_name TEXT NOT NULL,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)
    
    # Tabela de músicas dentro das playlists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlist_musicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            musica_id TEXT NOT NULL,
            titulo_musica TEXT,
            artista_musica TEXT,
            preview_url_musica TEXT,
            artista_id TEXT,
            album_cover_url TEXT,
            service_name TEXT NOT NULL,
            FOREIGN KEY (playlist_id) REFERENCES playlists_salvas (id) ON DELETE CASCADE
        )
    """)

    # Tabela de "gostos" (likes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlist_likes (
            playlist_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            data_like DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (playlist_id, usuario_id),
            FOREIGN KEY (playlist_id) REFERENCES playlists_salvas (id) ON DELETE CASCADE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    """)

    # Tabela de histórico de feedback
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_reproducao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            musica_id TEXT, 
            artista_id TEXT,
            rating INTEGER, 
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    """)
    
    # --- Tabelas para gestão de músicas locais (opcional) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS musicas (
            id INTEGER PRIMARY KEY, titulo TEXT, artista TEXT, album TEXT,
            caminho_arquivo TEXT UNIQUE NOT NULL
        )""")
    
    cursor.execute("CREATE TABLE IF NOT EXISTS generos (id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS musica_generos (
            musica_id INTEGER, 
            genero_id INTEGER, 
            FOREIGN KEY (musica_id) REFERENCES musicas (id), 
            FOREIGN KEY (genero_id) REFERENCES generos (id), 
            PRIMARY KEY (musica_id, genero_id)
        )""")

    cursor.execute("CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS musica_tags (
            musica_id INTEGER, 
            tag_id INTEGER, 
            FOREIGN KEY (musica_id) REFERENCES musicas (id), 
            FOREIGN KEY (tag_id) REFERENCES tags (id), 
            PRIMARY KEY (musica_id, tag_id)
        )""")
    
    conn.commit()
    print("\nEstrutura de tabelas genérica verificada/criada com sucesso.")

def processar_e_inserir_musicas(conn, pasta):
    """Escaneia uma pasta e insere músicas locais na tabela 'musicas'."""
    cursor = conn.cursor()
    print(f"\nA escutar a pasta '{pasta}' para músicas...")
    if not os.path.isdir(pasta):
        print(f"Aviso: Pasta '{pasta}' não encontrada. Foi criada, mas está vazia.")
        os.makedirs(pasta, exist_ok=True)
        return

    arquivos_processados = 0
    for nome_arquivo in os.listdir(pasta):
        if nome_arquivo.lower().endswith('.mp3'):
            caminho_completo = os.path.join(pasta, nome_arquivo)
            try:
                cursor.execute("SELECT id FROM musicas WHERE caminho_arquivo = ?", (caminho_completo,))
                if cursor.fetchone():
                    continue

                audio = EasyID3(caminho_completo)
                titulo = audio.get('title', [os.path.splitext(nome_arquivo)[0]])[0]
                artista = audio.get('artist', ['Artista Desconhecido'])[0]
                album = audio.get('album', ['Álbum Desconhecido'])[0]
                
                cursor.execute("INSERT INTO musicas (titulo, artista, album, caminho_arquivo) VALUES (?, ?, ?, ?)",
                               (titulo, artista, album, caminho_completo))
                
                print(f"Processado: {artista} - {titulo}")
                arquivos_processados += 1
            except ID3NoHeaderError:
                print(f"Aviso: O ficheiro '{nome_arquivo}' não possui cabeçalho ID3.")
            except Exception as e:
                print(f"Erro ao processar o ficheiro {nome_arquivo}: {e}")
    
    conn.commit()
    if arquivos_processados > 0:
        print(f"\n{arquivos_processados} nova(s) música(s) processada(s).")
    else:
        print("\nNenhuma música nova para processar.")

if __name__ == "__main__":
    print("A iniciar o script de setup da base de dados...")
    
    db_dir = os.path.dirname(DB_FILE)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    # Apaga a base de dados antiga para garantir que o novo esquema é aplicado
    if os.path.exists(DB_FILE):
        print(f"A remover a base de dados antiga: {DB_FILE}")
        os.remove(DB_FILE)
        
    conexao = sqlite3.connect(DB_FILE)
    
    criar_tabelas(conexao)
    processar_e_inserir_musicas(conexao, PASTA_DE_MUSICAS) # Garante que as músicas locais são processadas
    
    conexao.close()
    
    print(f"\nOperação de setup finalizada. A nova base de dados '{DB_FILE}' está pronta.")
