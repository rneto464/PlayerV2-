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
DB_FILE = os.path.join(ROOT_DIR, 'data', 'banco_musicas.db')
CAMINHO_CREDENCIAL_GOOGLE = os.path.join(ROOT_DIR, 'google-credentials.json')

# --- Inicialização da Aplicação Flask ---
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.urandom(24) 

def setup_application():
    """Inicializa todos os serviços e gestores e retorna-os num único dicionário de contexto."""
    print("A inicializar os gestores e o motor de recomendação...")
    try:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = CAMINHO_CREDENCIAL_GOOGLE
        vision_client = vision.ImageAnnotatorClient()
        db_connection = sqlite3.connect(DB_FILE, check_same_thread=False)

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
        
        return {
            "engine": rec_engine,
            "auth": {"spotify": auth_spotify, "youtube": auth_youtube},
            "services": {"spotify": service_spotify, "youtube": service_youtube},
            "db_connection": db_connection
        }
        
    except Exception as e:
        print(f"ERRO CRÍTICO AO INICIAR SERVIDOR: {e}"); sys.exit(1)

app_context = setup_application()
conn = app_context['db_connection']

# ===================================================
# Endpoints da Interface e Autenticação
# ===================================================
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
    spotify_auth_manager = app_context['auth']['spotify']
    oauth_manager = spotify_auth_manager.get_oauth_manager(session)
    auth_url = oauth_manager.get_authorize_url()
    return redirect(auth_url)

@app.route('/login/youtube')
def login_youtube():
    youtube_auth_manager = app_context['auth']['youtube']
    auth_url, state = youtube_auth_manager.get_auth_url()
    session['oauth_state'] = state
    return redirect(auth_url)

@app.route('/callback/spotify')
def callback_spotify():
    spotify_auth_manager = app_context['auth']['spotify']
    oauth_manager = spotify_auth_manager.get_oauth_manager(session)
    code = request.args.get('code')
    if code:
        try:
            token_info = spotify_auth_manager.get_token_from_code(oauth_manager, code)
            sp_user = spotify_auth_manager.get_user_client(token_info)
            user_info = sp_user.me()
            
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE service_user_id = ? AND service_name = 'spotify'", (user_info['id'],))
            user_row = cursor.fetchone()
            if not user_row:
                cursor.execute("INSERT INTO usuarios (service_user_id, service_name, display_name) VALUES (?, 'spotify', ?)",
                               (user_info['id'], user_info['display_name']))
                conn.commit(); db_user_id = cursor.lastrowid
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
    youtube_auth_manager = app_context['auth']['youtube']
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
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE service_user_id = ? AND service_name = 'youtube'", (user_id_yt,))
        user_row = cursor.fetchone()
        if not user_row:
            cursor.execute("INSERT INTO usuarios (service_user_id, service_name, display_name) VALUES (?, 'youtube', ?)",
                           (user_id_yt, display_name))
            conn.commit(); db_user_id = cursor.lastrowid
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
    active_service_name = session.get('service')
    return app_context['services'].get(active_service_name) if active_service_name else None

@app.route('/api/recommend_by_image', methods=['POST'])
def recommend_by_image_api():
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    engine = app_context['engine']; engine.music_service = _get_active_service()
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
    engine = app_context['engine']; engine.music_service = _get_active_service()
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
    active_service_name = session['service']
    active_service = app_context['services'][active_service_name]
    auth_manager = app_context['auth'][active_service_name]
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
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO playlists_salvas (usuario_id, nome_playlist, playlist_url, service_name) VALUES (?, ?, ?, ?)",
                       (session['internal_user_id'], playlist_name, playlist_url, active_service_name))
        conn.commit()
        return jsonify({"success": True, "message": f"Playlist '{playlist_name}' criada com sucesso!", "playlist_url": playlist_url})
    except Exception as e:
        conn.rollback(); print(f"Erro ao criar playlist: {e}"); return jsonify({"error": f"Erro ao criar a sua playlist: {e}"}), 500

@app.route('/api/local_playlists', methods=['GET'])
def get_local_playlists():
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    try:
        cursor = conn.cursor()
        playlists = [{"id": row[0], "name": row[1]} for row in cursor.execute("SELECT id, nome_playlist FROM playlists_salvas WHERE usuario_id = ? ORDER BY nome_playlist", (session['internal_user_id'],))]
        return jsonify(playlists)
    except Exception as e:
        print(f"Erro ao buscar playlists: {e}"); return jsonify({"error": "Erro interno."}), 500

@app.route('/api/local_playlists/<int:playlist_id>', methods=['GET'])
def get_local_playlist_tracks(playlist_id):
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    try:
        cursor = conn.cursor()
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
        cursor = conn.cursor()
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
        conn.commit(); return jsonify({"success": True, "message": "Playlist guardada!"})
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
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM playlists_salvas WHERE nome_playlist = ? AND usuario_id = ?", (new_name, session['internal_user_id']))
        if cursor.fetchone(): return jsonify({"error": "Nome já existe."}), 409
        cursor.execute("UPDATE playlists_salvas SET nome_playlist = ? WHERE id = ? AND usuario_id = ?", (new_name, playlist_id, session['internal_user_id']))
        conn.commit()
        return jsonify({"success": cursor.rowcount > 0})
    except Exception as e:
        print(f"Erro ao renomear: {e}"); return jsonify({"error": "Erro interno."}), 500

@app.route('/api/delete_local_playlist/<int:playlist_id>', methods=['DELETE'])
def delete_playlist_api(playlist_id):
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM playlists_salvas WHERE id = ? AND usuario_id = ?", (playlist_id, session['internal_user_id']))
        conn.commit()
        return jsonify({"success": cursor.rowcount > 0})
    except Exception as e:
        print(f"Erro ao apagar: {e}"); return jsonify({"error": "Erro interno."}), 500

@app.route('/api/community_playlists', methods=['GET'])
def get_community_playlists():
    if 'internal_user_id' not in session: return jsonify({"error": "Utilizador não autenticado."}), 401
    current_user_id = session['internal_user_id']
    try:
        cursor = conn.cursor()
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
        cursor = conn.cursor()
        if cursor.execute("SELECT 1 FROM playlist_likes WHERE playlist_id = ? AND usuario_id = ?", (playlist_id, user_id)).fetchone():
            cursor.execute("DELETE FROM playlist_likes WHERE playlist_id = ? AND usuario_id = ?", (playlist_id, user_id)); liked = False
        else:
            cursor.execute("INSERT INTO playlist_likes (playlist_id, usuario_id) VALUES (?, ?)", (playlist_id, user_id)); liked = True
        conn.commit()
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
    
    engine = app_context['engine']
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
    
    engine = app_context['engine']
    # Passa o ID interno para o motor
    sucesso = engine.registrar_feedback_playlist_engine(lista_de_musicas, rating, session['internal_user_id'])
    
    return jsonify({"success": sucesso})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
