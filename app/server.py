# Nome do ficheiro: app/server.py
import os
import sqlite3
import uuid
import sys
from flask import Flask, request, jsonify, render_template, redirect, session, url_for
from google.cloud import vision
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Permite o uso de HTTP para o fluxo OAuth em ambiente local
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Importações refatoradas
from .spotify_auth_manager import SpotifyAuthManager
from .youtube_auth_manager import YouTubeAuthManager
from .recommendation_engine import RecommendationEngine
from .services.spotify_service import SpotifyService
from .services.youtube_service import YouTubeMusicService
from . import config_credentials as creds 

# --- Configurações de Caminhos ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Detecta ambiente Vercel (verifica variáveis de ambiente comuns da Vercel)
IS_VERCEL = (
    os.environ.get('VERCEL') == '1' or 
    os.environ.get('VERCEL_ENV') is not None or
    '/var/task' in os.path.abspath(__file__) or
    os.path.exists('/var/task')
)

# Na Vercel, usa /tmp para banco de dados (única área writeable)
# Em ambiente local, usa o diretório data/
if IS_VERCEL:
    DB_DIR = '/tmp'
    print(f"Ambiente Vercel detectado. Usando /tmp para banco de dados.")
else:
    DB_DIR = os.path.join(ROOT_DIR, 'data')
    os.makedirs(DB_DIR, exist_ok=True)

DB_FILE = os.path.join(DB_DIR, 'banco_musicas.db')
CAMINHO_CREDENCIAL_GOOGLE = os.path.join(ROOT_DIR, 'google-credentials.json')

# --- Inicialização da Aplicação Flask ---
# Usa caminhos absolutos para templates e static
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
static_dir = os.path.join(os.path.dirname(__file__), 'static')
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())

# Variável global para armazenar o contexto da aplicação (lazy loading)
app_context = None
conn = None

def setup_application():
    """Inicializa todos os serviços e gestores e retorna-os num único dicionário de contexto."""
    global app_context, conn
    
    if app_context is not None:
        return app_context
    
    print("A inicializar os gestores e o motor de recomendação...")
    print(f"Ambiente Vercel detectado: {IS_VERCEL}")
    print(f"DB_DIR configurado: {DB_DIR}")
    print(f"DB_FILE configurado: {DB_FILE}")
    
    try:
        # Configura credenciais do Google (suporta múltiplas formas)
        google_creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        google_creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        
        print(f"GOOGLE_APPLICATION_CREDENTIALS: {'Definido' if google_creds_path else 'Não definido'}")
        print(f"GOOGLE_CREDENTIALS_JSON: {'Definido' if google_creds_json else 'Não definido'}")
        
        if google_creds_json:
            # Se as credenciais estão em formato JSON na variável de ambiente
            # Cria um arquivo temporário com as credenciais
            import json
            try:
                # Valida se é JSON válido
                creds_data = json.loads(google_creds_json)
                # Cria arquivo temporário com as credenciais
                if IS_VERCEL:
                    temp_creds_path = '/tmp/google-credentials.json'
                else:
                    temp_creds_path = os.path.join(ROOT_DIR, 'google-credentials-temp.json')
                
                with open(temp_creds_path, 'w') as f:
                    json.dump(creds_data, f)
                
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_creds_path
                print("Credenciais do Google carregadas a partir da variável de ambiente GOOGLE_CREDENTIALS_JSON")
            except json.JSONDecodeError as e:
                print(f"ERRO: GOOGLE_CREDENTIALS_JSON contém JSON inválido: {e}")
            except Exception as e:
                print(f"ERRO ao processar GOOGLE_CREDENTIALS_JSON: {e}")
        elif google_creds_path:
            # Já está configurado via variável de ambiente (caminho do arquivo)
            print(f"Usando credenciais do Google do caminho: {google_creds_path}")
        elif os.path.exists(CAMINHO_CREDENCIAL_GOOGLE):
            # Usa arquivo local se existir
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = CAMINHO_CREDENCIAL_GOOGLE
            print(f"Usando credenciais do Google do arquivo local: {CAMINHO_CREDENCIAL_GOOGLE}")
        else:
            print("AVISO: Credenciais do Google não encontradas. Algumas funcionalidades podem não funcionar.")
            print("Para configurar, adicione uma das seguintes variáveis de ambiente na Vercel:")
            print("  - GOOGLE_APPLICATION_CREDENTIALS: caminho para o arquivo JSON")
            print("  - GOOGLE_CREDENTIALS_JSON: conteúdo completo do arquivo JSON como string")
        
        # Inicializa cliente Vision (pode falhar se credenciais não estiverem configuradas)
        vision_client = None
        try:
            vision_client = vision.ImageAnnotatorClient()
        except Exception as e:
            print(f"AVISO: Não foi possível inicializar o cliente Vision: {e}")
        
        # Determina o caminho do banco de dados (sempre usa /tmp na Vercel)
        if IS_VERCEL:
            db_file_path = '/tmp/banco_musicas.db'
            db_dir = '/tmp'
            print(f"[DEBUG] Ambiente Vercel: usando {db_file_path}")
        else:
            db_file_path = DB_FILE
            db_dir = os.path.dirname(DB_FILE)
            print(f"[DEBUG] Ambiente local: usando {db_file_path}")
        
        # Garante que o diretório do banco existe
        try:
            os.makedirs(db_dir, exist_ok=True)
            print(f"Diretório do banco verificado: {db_dir}")
            
            # Verifica se o diretório é writeable
            test_file = os.path.join(db_dir, '.test_write')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                print(f"Diretório {db_dir} é writeable")
            except Exception as e:
                print(f"AVISO: Diretório {db_dir} não é writeable: {e}")
                # Se não for writeable e não estiver na Vercel, tenta /tmp
                if not IS_VERCEL:
                    db_file_path = '/tmp/banco_musicas.db'
                    db_dir = '/tmp'
                    os.makedirs(db_dir, exist_ok=True)
                    print(f"Usando /tmp como fallback: {db_file_path}")
        except Exception as e:
            print(f"AVISO: Não foi possível criar diretório {db_dir}: {e}")
            # Se falhar e não estiver na Vercel, tenta /tmp
            if not IS_VERCEL:
                db_file_path = '/tmp/banco_musicas.db'
                db_dir = '/tmp'
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    print(f"Usando /tmp como fallback: {db_file_path}")
                except Exception as e2:
                    print(f"ERRO CRÍTICO: Não foi possível criar diretório em /tmp: {e2}")
                    raise
        
        # Conecta ao banco de dados
        try:
            db_connection = sqlite3.connect(db_file_path, check_same_thread=False)
            print(f"Banco de dados conectado: {db_file_path}")
            
            # Inicializa as tabelas se o banco estiver vazio
            cursor = db_connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'")
            if not cursor.fetchone():
                print("Inicializando estrutura do banco de dados...")
                _criar_tabelas(db_connection)
        except Exception as e:
            print(f"ERRO: Não foi possível conectar ao banco de dados em {DB_FILE}: {e}")
            import traceback
            traceback.print_exc()
            raise

        auth_spotify = SpotifyAuthManager()
        auth_youtube = YouTubeAuthManager()
        
        sp_app_client = auth_spotify.get_app_client()
        service_spotify = SpotifyService(spotify_client=sp_app_client)
        # yt-dlp não requer chave de API para buscas, mas ainda é útil para criar playlists
        youtube_api_key = getattr(creds, 'YOUTUBE_API_KEY', None)
        service_youtube = YouTubeMusicService(developer_key=youtube_api_key)

        rec_engine = RecommendationEngine(
            vision_client=vision_client, 
            db_connection=db_connection
        )
        
        print("Servidor pronto para receber pedidos.")
        
        app_context = {
            "engine": rec_engine,
            "auth": {"spotify": auth_spotify, "youtube": auth_youtube},
            "services": {"spotify": service_spotify, "youtube": service_youtube},
            "db_connection": db_connection
        }
        conn = db_connection
        return app_context
        
    except Exception as e:
        print(f"ERRO CRÍTICO AO INICIAR SERVIDOR: {e}")
        import traceback
        traceback.print_exc()
        # Não faz sys.exit() para permitir que a Vercel trate o erro
        raise

def _criar_tabelas(conn):
    """Cria todas as tabelas necessárias se não existirem."""
    cursor = conn.cursor()
    
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlists_salvas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nome_playlist TEXT NOT NULL,
            playlist_url TEXT,
            service_name TEXT NOT NULL,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)
    
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
    
    conn.commit()
    print("Tabelas criadas/verificadas com sucesso.")

def get_app_context():
    """Obtém o contexto da aplicação, inicializando se necessário."""
    if app_context is None:
        return setup_application()
    return app_context

# ===================================================
# Endpoints da Interface e Autenticação
# ===================================================
@app.route('/favicon.ico')
def favicon():
    """Rota para favicon - retorna 204 No Content"""
    return '', 204

@app.route('/')
def welcome():
    if 'internal_user_id' in session: return redirect(url_for('player'))
    return render_template('welcome.html')

@app.route('/player')
def player():
    if 'internal_user_id' not in session: return redirect(url_for('welcome'))
    return render_template('player.html')

@app.route('/community')
def community():
    if 'internal_user_id' not in session: return redirect('/')
    return render_template('community.html')

@app.route('/login/spotify')
def login_spotify():
    ctx = get_app_context()
    spotify_auth_manager = ctx['auth']['spotify']
    oauth_manager = spotify_auth_manager.get_oauth_manager(session)
    auth_url = oauth_manager.get_authorize_url()
    return redirect(auth_url)

@app.route('/login/youtube')
def login_youtube():
    ctx = get_app_context()
    youtube_auth_manager = ctx['auth']['youtube']
    auth_url, state = youtube_auth_manager.get_auth_url()
    session['oauth_state'] = state
    return redirect(auth_url)

@app.route('/callback/spotify')
def callback_spotify():
    ctx = get_app_context()
    spotify_auth_manager = ctx['auth']['spotify']
    oauth_manager = spotify_auth_manager.get_oauth_manager(session)
    code = request.args.get('code')
    if code:
        try:
            token_info = spotify_auth_manager.get_token_from_code(oauth_manager, code)
            sp_user = spotify_auth_manager.get_user_client(token_info)
            user_info = sp_user.me()
            
            db_conn = ctx['db_connection']
            cursor = db_conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE service_user_id = ? AND service_name = 'spotify'", (user_info['id'],))
            user_row = cursor.fetchone()
            if not user_row:
                cursor.execute("INSERT INTO usuarios (service_user_id, service_name, display_name) VALUES (?, 'spotify', ?)",
                               (user_info['id'], user_info['display_name']))
                db_conn.commit(); db_user_id = cursor.lastrowid
            else:
                db_user_id = user_row[0]
            
            session.update({
                'service': 'spotify', 'internal_user_id': db_user_id,
                'service_user_id': user_info['id'], 
                'display_name': user_info['display_name'], 'token_info': token_info
            })
            return redirect('/player')
        except Exception as e:
            print(f"Erro no callback do Spotify: {e}"); return "Erro ao obter o token de acesso.", 400
    return "Erro: Nenhum código de autorização fornecido.", 400

@app.route('/callback/youtube')
def callback_youtube():
    ctx = get_app_context()
    youtube_auth_manager = ctx['auth']['youtube']
    state = session.pop('oauth_state', None)
    if state is None or state != request.args.get('state'): return 'Invalid state parameter.', 400
    try:
        token_info = youtube_auth_manager.get_token_from_code(request.url, state)
        credentials = Credentials(**token_info)
        youtube_user_client = build('youtube', 'v3', credentials=credentials)
        response = youtube_user_client.channels().list(part='snippet', mine=True).execute()
        if not response.get('items'): return "A sua conta Google não tem um canal do YouTube.", 400
        user_channel = response['items'][0]
        user_id_yt, display_name = user_channel['id'], user_channel['snippet']['title']
        db_conn = ctx['db_connection']
        cursor = db_conn.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE service_user_id = ? AND service_name = 'youtube'", (user_id_yt,))
        user_row = cursor.fetchone()
        if not user_row:
            cursor.execute("INSERT INTO usuarios (service_user_id, service_name, display_name) VALUES (?, 'youtube', ?)",
                           (user_id_yt, display_name))
            db_conn.commit(); db_user_id = cursor.lastrowid
        else:
            db_user_id = user_row[0]
        session.update({
            'service': 'youtube', 'internal_user_id': db_user_id,
            'service_user_id': user_id_yt,
            'display_name': display_name, 'token_info': token_info
        })
        return redirect('/player')
    except Exception as e:
        print(f"Erro no callback do YouTube: {e}"); return "Erro ao obter o token de acesso do YouTube.", 400

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

@app.route('/api/user_status')
def user_status():
    if 'internal_user_id' in session:
        return jsonify({"logged_in": True, "display_name": session.get('display_name'), "service": session.get('service')})
    return jsonify({"logged_in": False})

def _get_active_service():
    ctx = get_app_context()
    active_service_name = session.get('service')
    return ctx['services'].get(active_service_name) if active_service_name else None

@app.route('/api/recommend_by_image', methods=['POST'])
def recommend_by_image_api():
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    ctx = get_app_context()
    engine = ctx['engine']; engine.music_service = _get_active_service()
    if not engine.music_service: return jsonify({"error": "Serviço de música não encontrado."}), 500
    if 'image' not in request.files: return jsonify({"error": "Nenhum ficheiro de imagem."}), 400
    file = request.files['image']
    if not file or file.filename == '': return jsonify({"error": "Ficheiro inválido."}), 400
    temp_dir = "temp_uploads"; os.makedirs(temp_dir, exist_ok=True)
    filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
    temp_path = os.path.join(temp_dir, filename); file.save(temp_path)
    tags, playlist_title = engine.analisar_imagem_e_obter_tags(temp_path)
    os.remove(temp_path)
    if not tags: return jsonify({"error": "Não foi possível analisar a imagem."}), 500
    recomendacoes = engine.recomendar_musicas_por_tags(tags, is_redo=False)
    if recomendacoes is None: return jsonify({"error": "Erro ao obter recomendações."}), 500
    return jsonify({"ambiente_detetado": tags, "recomendacoes": recomendacoes, "playlist_title": playlist_title})

@app.route('/api/recommend_from_tags', methods=['POST'])
def recommend_from_tags_api():
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    ctx = get_app_context()
    engine = ctx['engine']; engine.music_service = _get_active_service()
    if not engine.music_service: return jsonify({"error": "Serviço de música não encontrado."}), 500
    data = request.get_json(); tags = data.get('tags')
    if not tags: return jsonify({"error": "Nenhuma tag fornecida."}), 400
    recomendacoes = engine.recomendar_musicas_por_tags(tags, is_redo=True) 
    if recomendacoes is None: return jsonify({"error": "Erro ao obter recomendações."}), 500
    return jsonify({"ambiente_detetado": tags, "recomendacoes": recomendacoes, "playlist_title": f"Novas recomendações para: {', '.join(map(str, tags))}"})

@app.route('/api/create_playlist', methods=['POST'])
def create_playlist_api():
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    data = request.get_json()
    playlist_name, tracks = data.get('name'), data.get('tracks')
    if not playlist_name or not tracks: return jsonify({"error": "Dados em falta."}), 400
    ctx = get_app_context()
    active_service_name = session['service']
    active_service = ctx['services'][active_service_name]
    auth_manager = ctx['auth'][active_service_name]
    try:
        user_client = None
        if active_service_name == 'spotify':
            oauth_manager = auth_manager.get_oauth_manager(session)
            token_info = session.get('token_info')
            if oauth_manager.is_token_expired(token_info):
                token_info = oauth_manager.refresh_access_token(token_info['refresh_token'])
                session['token_info'] = token_info
            user_client = auth_manager.get_user_client(token_info)
        elif active_service_name == 'youtube':
            credentials = Credentials(**session['token_info'])
            user_client = build('youtube', 'v3', credentials=credentials)
        if not user_client: return jsonify({"error": "Não foi possível autenticar o cliente."}), 500
        nova_playlist = active_service.create_playlist(user_client=user_client, playlist_name=playlist_name, tracks=tracks)
        # Corrigido: suporta tanto Spotify quanto YouTube
        if active_service_name == 'spotify':
            playlist_url = nova_playlist.get('external_urls', {}).get('spotify', '')
        else:  # YouTube
            playlist_url = nova_playlist.get('external_urls', {}).get('youtube') or nova_playlist.get('external_urls', {}).get('spotify', '')
        if not playlist_url:
            playlist_url = f"https://www.youtube.com/playlist?list={nova_playlist.get('id', '')}" if active_service_name == 'youtube' else ''
        db_conn = ctx['db_connection']
        cursor = db_conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO playlists_salvas (usuario_id, nome_playlist, playlist_url, service_name) VALUES (?, ?, ?, ?)",
                       (session['internal_user_id'], playlist_name, playlist_url, active_service_name))
        db_conn.commit()
        return jsonify({"success": True, "message": f"Playlist '{playlist_name}' criada com sucesso!", "playlist_url": playlist_url})
    except Exception as e:
        ctx = get_app_context()
        ctx['db_connection'].rollback(); print(f"Erro ao criar playlist: {e}"); return jsonify({"error": f"Erro ao criar a sua playlist: {e}"}), 500

@app.route('/api/local_playlists', methods=['GET'])
def get_local_playlists():
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    try:
        ctx = get_app_context()
        cursor = ctx['db_connection'].cursor()
        playlists = [{"id": row[0], "name": row[1]} for row in cursor.execute("SELECT id, nome_playlist FROM playlists_salvas WHERE usuario_id = ? ORDER BY nome_playlist", (session['internal_user_id'],))]
        return jsonify(playlists)
    except Exception as e:
        print(f"Erro ao buscar playlists: {e}"); return jsonify({"error": "Erro interno."}), 500

@app.route('/api/local_playlists/<int:playlist_id>', methods=['GET'])
def get_local_playlist_tracks(playlist_id):
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    try:
        ctx = get_app_context()
        cursor = ctx['db_connection'].cursor()
        cursor.execute("SELECT id FROM playlists_salvas WHERE id = ? AND usuario_id = ?", (playlist_id, session['internal_user_id']))
        if not cursor.fetchone(): return jsonify({"error": "Não encontrado."}), 404
        cursor.execute("SELECT musica_id, titulo_musica, artista_musica, preview_url_musica, artista_id, service_name FROM playlist_musicas WHERE playlist_id = ?", (playlist_id,))
        musicas = [{'spotify_id': r[0], 'titulo': r[1], 'artista': r[2], 'preview_url': r[3], 'artista_id': r[4], 'service_name': r[5]} for r in cursor.fetchall()]
        return jsonify(musicas)
    except Exception as e:
        print(f"Erro ao buscar faixas: {e}"); return jsonify({"error": "Erro interno."}), 500

@app.route('/api/local_playlists', methods=['POST'])
def create_local_playlist():
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    data = request.get_json()
    playlist_name, tracks = data.get('name'), data.get('tracks')
    if not playlist_name or not tracks: return jsonify({"error": "Dados em falta."}), 400
    active_service_name = session['service']
    try:
        ctx = get_app_context()
        cursor = ctx['db_connection'].cursor()
        # Verifica se a playlist já existe
        cursor.execute("SELECT id FROM playlists_salvas WHERE usuario_id = ? AND nome_playlist = ? AND service_name = ?", (session['internal_user_id'], playlist_name, active_service_name))
        existing = cursor.fetchone()
        if existing:
            playlist_id = existing[0]
            # Remove músicas existentes para substituir
            cursor.execute("DELETE FROM playlist_musicas WHERE playlist_id = ?", (playlist_id,))
        else:
            cursor.execute("INSERT INTO playlists_salvas (usuario_id, nome_playlist, service_name) VALUES (?, ?, ?)", (session['internal_user_id'], playlist_name, active_service_name))
        playlist_id = cursor.lastrowid
        for track in tracks:
            cursor.execute("INSERT INTO playlist_musicas (playlist_id, musica_id, titulo_musica, artista_musica, preview_url_musica, artista_id, album_cover_url, service_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (playlist_id, track.get('spotify_id'), track.get('titulo'), track.get('artista'), track.get('preview_url'), track.get('artista_id'), track.get('album_cover_url'), active_service_name))
        ctx['db_connection'].commit(); return jsonify({"success": True, "message": "Playlist guardada!"})
    except sqlite3.IntegrityError: return jsonify({"error": f"Já existe uma playlist com o nome '{playlist_name}'."}), 409
    except Exception as e:
        print(f"Erro ao guardar playlist: {e}"); return jsonify({"error": "Erro interno."}), 500

@app.route('/api/rename_local_playlist/<int:playlist_id>', methods=['POST'])
def rename_playlist_api(playlist_id):
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    data = request.get_json()
    new_name = data.get('new_name', '').strip()
    if not new_name: return jsonify({"error": "Nome inválido."}), 400
    try:
        ctx = get_app_context()
        cursor = ctx['db_connection'].cursor()
        cursor.execute("SELECT id FROM playlists_salvas WHERE nome_playlist = ? AND usuario_id = ?", (new_name, session['internal_user_id']))
        if cursor.fetchone(): return jsonify({"error": "Nome já existe."}), 409
        cursor.execute("UPDATE playlists_salvas SET nome_playlist = ? WHERE id = ? AND usuario_id = ?", (new_name, playlist_id, session['internal_user_id']))
        ctx['db_connection'].commit()
        return jsonify({"success": cursor.rowcount > 0})
    except Exception as e:
        print(f"Erro ao renomear: {e}"); return jsonify({"error": "Erro interno."}), 500

@app.route('/api/delete_local_playlist/<int:playlist_id>', methods=['DELETE'])
def delete_playlist_api(playlist_id):
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    try:
        ctx = get_app_context()
        cursor = ctx['db_connection'].cursor()
        cursor.execute("DELETE FROM playlists_salvas WHERE id = ? AND usuario_id = ?", (playlist_id, session['internal_user_id']))
        ctx['db_connection'].commit()
        return jsonify({"success": cursor.rowcount > 0})
    except Exception as e:
        print(f"Erro ao apagar: {e}"); return jsonify({"error": "Erro interno."}), 500

@app.route('/api/community_playlists', methods=['GET'])
def get_community_playlists():
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    current_user_id = session['internal_user_id']
    try:
        ctx = get_app_context()
        cursor = ctx['db_connection'].cursor()
        query = "SELECT p.id, p.nome_playlist, u.display_name, p.playlist_url, p.service_name FROM playlists_salvas p JOIN usuarios u ON p.usuario_id = u.id ORDER BY p.data_criacao DESC"
        playlists = []
        for p_id, p_name, p_creator, p_url, p_service in cursor.execute(query).fetchall():
            covers = [r[0] for r in cursor.execute("SELECT album_cover_url FROM playlist_musicas WHERE playlist_id = ? AND album_cover_url IS NOT NULL LIMIT 4", (p_id,))]
            like_count = cursor.execute("SELECT COUNT(*) FROM playlist_likes WHERE playlist_id = ?", (p_id,)).fetchone()[0]
            user_has_liked = cursor.execute("SELECT 1 FROM playlist_likes WHERE playlist_id = ? AND usuario_id = ?", (p_id, current_user_id)).fetchone() is not None
            playlists.append({"id": p_id, "name": p_name, "creator": p_creator, "playlist_url": p_url, "service_name": p_service, "cover_urls": covers, "like_count": like_count, "user_has_liked": user_has_liked})
        return jsonify(playlists)
    except Exception as e:
        print(f"Erro ao buscar comunidade: {e}"); return jsonify({"error": "Erro interno."}), 500

@app.route('/api/playlist/<int:playlist_id>/toggle_like', methods=['POST'])
def toggle_playlist_like(playlist_id):
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    user_id = session['internal_user_id']
    try:
        ctx = get_app_context()
        cursor = ctx['db_connection'].cursor()
        if cursor.execute("SELECT 1 FROM playlist_likes WHERE playlist_id = ? AND usuario_id = ?", (playlist_id, user_id)).fetchone():
            cursor.execute("DELETE FROM playlist_likes WHERE playlist_id = ? AND usuario_id = ?", (playlist_id, user_id)); liked = False
        else:
            cursor.execute("INSERT INTO playlist_likes (playlist_id, usuario_id) VALUES (?, ?)", (playlist_id, user_id)); liked = True
        ctx['db_connection'].commit()
        like_count = cursor.execute("SELECT COUNT(*) FROM playlist_likes WHERE playlist_id = ?", (playlist_id,)).fetchone()[0]
        return jsonify({"success": True, "liked": liked, "new_like_count": like_count})
    except Exception as e:
        print(f"Erro ao dar like: {e}"); return jsonify({"error": "Erro interno."}), 500
    

@app.route('/api/feedback', methods=['POST'])
def feedback_api():
    # --- CORREÇÃO AQUI: Usa 'internal_user_id' ---
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    
    data = request.get_json()
    musica_info, rating = data.get('track_info'), data.get('rating')
    if not musica_info or rating not in [1, -1]: return jsonify({"error": "Dados inválidos."}), 400
    
    ctx = get_app_context()
    engine = ctx['engine']
    # Passa o ID interno para o motor
    sucesso = engine.registrar_feedback_engine(musica_info, rating, session['internal_user_id'])
    
    return jsonify({"success": sucesso})

@app.route('/api/playlist_feedback', methods=['POST'])
def playlist_feedback_api():
    # --- CORREÇÃO AQUI: Usa 'internal_user_id' ---
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    
    data = request.get_json()
    lista_de_musicas, rating = data.get('tracks'), data.get('rating')
    if not lista_de_musicas or rating not in [1, -1]: return jsonify({"error": "Dados inválidos."}), 400
    
    ctx = get_app_context()
    engine = ctx['engine']
    # Passa o ID interno para o motor
    sucesso = engine.registrar_feedback_playlist_engine(lista_de_musicas, rating, session['internal_user_id'])
    
    return jsonify({"success": sucesso})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
