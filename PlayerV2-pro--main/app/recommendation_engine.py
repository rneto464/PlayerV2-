# Nome do ficheiro: app/recommendation_engine.py
import os
import random
import sqlite3
import base64
import json
import requests
import time
from google.cloud import vision
from .services.spotify_service import SpotifyService
from .services.youtube_service import YouTubeMusicService
from . import config_credentials as creds

def chamar_gemini(payload, api_url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, json=payload, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"[Engine] Limite atingido, tentando novamente em {wait}s...")
                time.sleep(wait)
                continue
            print(f"[Engine] Erro ao chamar Gemini: {e}")
            return None
        except Exception as e:
            print(f"[Engine] Erro inesperado: {e}")
            return None


class RecommendationEngine:
    def __init__(self, vision_client, db_connection):
        """
        Inicializa o motor, definindo o serviço de música dinamicamente por pedido.
        Também carrega a lista de géneros disponíveis do Spotify a partir de um ficheiro.
        """
        self.vision_client = vision_client
        self.conn = db_connection
        self.gemini_api_key = creds.GEMINI_API_KEY
        self.music_service = None
        
        # Carrega a lista de géneros válidos do Spotify para validação
        self.available_spotify_genres = set()
        try:
            print("[Engine] A carregar a lista de géneros do Spotify a partir do ficheiro local...")
            current_dir = os.path.dirname(os.path.abspath(__file__))
            genres_file_path = os.path.join(current_dir, '..', 'data', 'spotify_genres.txt')
            with open(genres_file_path, 'r') as f:
                self.available_spotify_genres = set(f.read().strip().split(','))
            print(f"[Engine] Carregados {len(self.available_spotify_genres)} géneros do Spotify.")
        except Exception as e:
            print(f"[Engine] AVISO: Não foi possível carregar o ficheiro de géneros do Spotify. Erro: {e}")

    def analisar_imagem_e_obter_tags(self, filepath):
        """Usa a Vision API para contexto e o Gemini para emoção/título."""
        if not self.vision_client:
            print("[Engine] Cliente Google Vision não inicializado.")
            return None, None
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            
            tags_coletadas = set()
            
            print("[Engine] A executar análise de contexto com Vision API...")
            response_web = self.vision_client.web_detection(image=vision.Image(content=content))
            if response_web.web_detection.web_entities:
                for entity in response_web.web_detection.web_entities[:5]:
                    tags_coletadas.add(entity.description.lower())
            
            print("[Engine] A executar análise de emoção e título com Gemini...")
            emotional_tags, playlist_title = self._analisar_emocao_e_titulo_com_ia(content)
            if emotional_tags:
                tags_coletadas.update(emotional_tags)

            if not tags_coletadas:
                print("[Engine] Nenhuma tag detetada.")
                return None, None
                
            final_tags = list(tags_coletadas)
            print(f"[Engine] Tags Finais Combinadas (Contexto + Emoção): {final_tags}")
            return final_tags, playlist_title

        except Exception as e:
            print(f"[Engine] Erro ao analisar imagem: {e}")
            return None, None

    def _analisar_emocao_e_titulo_com_ia(self, image_content):
        """Usa o Gemini (multimodal) para obter tags de emoção e um título para a playlist."""
        if not self.gemini_api_key: return [], "Playlist Sugerida"
        
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        prompt = ("From this image, provide two things in JSON format:\n"
                  "1. A 'playlist_title' (a short, creative, 3-5 word title for a playlist that captures the image's essence).\n"
                  "2. A 'mood_tags' list (3-5 keywords describing the overall emotion and mood).\n"
                  "Example: {\"playlist_title\": \"Sunset Chill Vibes\", \"mood_tags\": [\"calm\", \"nostalgic\", \"serene\"]}")
        
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.gemini_api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": image_base64}}]}]}
        
        try:
            response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=20)
            response.raise_for_status()
            result = response.json()
            if result.get('candidates'):
                json_string = result['candidates'][0]['content']['parts'][0]['text'].replace('```json', '').replace('```', '').strip()
                data = json.loads(json_string)
                emotional_tags = data.get("mood_tags", [])
                playlist_title = data.get("playlist_title", "Playlist Sugerida")
                print(f"[Engine] Título da Playlist do Gemini: {playlist_title}")
                print(f"[Engine] Tags de emoção do Gemini: {emotional_tags}")
                return emotional_tags, playlist_title
            return [], "Playlist Sugerida"
        except Exception as e:
            print(f"[Engine] Erro ao analisar emoção com Gemini: {e}")
            return [], "Playlist Sugerida"

   
    def _gerar_consultas_youtube_com_gemini(self, tags, limit=7):
        """Gera sugestões de músicas ('Artista - Título') para o YouTube."""
        if not self.gemini_api_key: return []
        prompt = (f"Based on the following tags describing an image: {tags}. "
                  f"List {limit} real, well-known songs that fit this mood. "
                  "Format the response as a simple comma-separated list of 'Artist - Song Title'.\n"
                  "Example: Bon Iver - Holocene, The xx - Intro, Cigarettes After Sex - Apocalypse")
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.gemini_api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
            response.raise_for_status()
            result = response.json()
            if result.get('candidates'):
                text_response = result['candidates'][0]['content']['parts'][0]['text']
                queries = [q.strip() for q in text_response.split(',') if q.strip()]
                print(f"[Engine] Consultas de música geradas para o YouTube: {queries}")
                return queries
            return []
        except Exception as e:
            print(f"[Engine] Erro ao gerar consultas para o YouTube: {e}"); return []

    
    

    def _gerar_sementes_spotify_com_gemini(self, tags):
        """Usa o Gemini para gerar sementes ricas (géneros, características) para o Spotify."""
        if not self.gemini_api_key: return {}
        prompt = (f"You are a Spotify playlist expert. Based on these tags: {tags}, create a JSON object with seeds for Spotify's recommendation API. "
                  "Include 'seed_genres' (a list of 1-2 valid genres from Spotify's official list) "
                  "and optional target audio features like 'target_energy' (0.0-1.0), 'target_danceability' (0.0-1.0), or 'target_valence' (a measure of positivity, 0.0-1.0). "
                  "Example for tags ['party', 'night', 'happy']: {\"seed_genres\": [\"dance\", \"pop\"], \"target_energy\": 0.8, \"target_danceability\": 0.9}\n"
                  "Example for tags ['rain', 'sad', 'lo-fi']: {\"seed_genres\": [\"ambient\", \"sad\"], \"target_energy\": 0.2, \"target_acousticness\": 0.8}")
        
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.gemini_api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
            response.raise_for_status()
            result = response.json()
            if result.get('candidates'):
                json_string = result['candidates'][0]['content']['parts'][0]['text'].replace('```json', '').replace('```', '').strip()
                seeds = json.loads(json_string)
                
                # Validação dos géneros retornados pela IA
                if 'seed_genres' in seeds and self.available_spotify_genres:
                    seeds['seed_genres'] = [g for g in seeds['seed_genres'] if g in self.available_spotify_genres]
                    if not seeds['seed_genres']: del seeds['seed_genres']
                
                print(f"[Engine] Sementes geradas para o Spotify: {seeds}")
                return seeds
            return {}
        except Exception as e:
            print(f"[Engine] Erro ao gerar sementes para o Spotify: {e}"); return {}
        

    def recomendar_musicas_por_tags(self, tags, market='BR', limit=25, is_redo=False):
        if not self.music_service:
            print("[Engine] Serviço de música não inicializado.")
            return None
        if not tags:
            print("[Engine] Nenhuma tag fornecida.")
            return []

        if isinstance(self.music_service, SpotifyService):
            print("[Engine] A usar a estratégia do Spotify (Busca com IA).")
            query_musical = self._gerar_prompt_musical_spotify(tags, is_redo)
            tracks = self.music_service.search_tracks(query=query_musical, limit=limit, market=market)
            if tracks is None:
                return None
            return self._processar_faixas_spotify(tracks, limit)

        elif isinstance(self.music_service, YouTubeMusicService):
            print("[Engine] A usar a estratégia do YouTube (Sugestões de músicas da IA).")
            song_queries = self._gerar_consultas_youtube_com_gemini(tags, limit=limit)
            if not song_queries:
                return []

            youtube_tracks = []
            for query in song_queries:
                if len(youtube_tracks) >= limit:
                    break
                results = self.music_service.search_tracks(query=query, limit=1)
                if results:
                    youtube_tracks.extend(results)

            return youtube_tracks

        return []

    def _processar_faixas_spotify(self, tracks, limit=25):
        musicas_processadas = []
        ids_adicionados = set()
        palavras_instrumentais = [
            'instrumental', 'karaoke', 'backing track', 'versão instrumental', 'versao instrumental',
            'instrumental version', 'só a voz', 'no vocal', 'sem vocal', 'acoustic', 'acústica',
            'piano solo', 'guitar solo', 'lounge', 'chillhop', 'lo-fi', 'beat'
        ]

        def is_instrumental(item):
            nome = (item.get('name') or '').lower()
            artistas = [a.get('name', '').lower() for a in item.get('artists', [])]
            for palavra in palavras_instrumentais:
                if palavra in nome or any(palavra in artista for artista in artistas):
                    return True
            return False

        for item in tracks:
            if len(musicas_processadas) >= limit:
                break
            if not item or not item.get('artists') or not item.get('id'):
                continue
            if is_instrumental(item):
                continue
            spotify_id = item.get('id')
            if spotify_id in ids_adicionados:
                continue
            artists_data = item.get('artists', [])
            album_images = item.get('album', {}).get('images', [])
            musica = {
                'titulo': item.get('name'),
                'artista': artists_data[0].get('name') if artists_data else 'N/A',
                'artista_id': artists_data[0].get('id') if artists_data else None,
                'preview_url': item.get('preview_url'),
                'spotify_id': spotify_id,
                'album_cover_url': album_images[0]['url'] if album_images else None,
                'service': 'spotify'
            }
            musicas_processadas.append(musica)
            ids_adicionados.add(spotify_id)
        return musicas_processadas
    

    def _gerar_prompt_musical_spotify(self, tags, is_redo=False):
        """Gera um prompt de busca criativo para o Spotify."""
        if not self.gemini_api_key: return " ".join(tags[:3])
        redo_instruction = "Give me a COMPLETELY DIFFERENT and UNEXPECTED music prompt for these tags. Think outside the box." if is_redo else ""
        prompt = (f"Given these tags describing an image: {tags}. "
                f"{redo_instruction} "
                "Generate a short, creative prompt for a music playlist. "
                "Examples: 'upbeat indie pop for a sunny beach day', 'lo-fi chill beats for a rainy city night'")
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.gemini_api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
            response.raise_for_status()
            result = response.json()
            if result.get('candidates'): return result['candidates'][0]['content']['parts'][0]['text'].strip()
            return " ".join(tags[:3])
        except Exception as e:
            print(f"[Engine] Erro ao gerar prompt para o Spotify: {e}"); return " ".join(tags[:3])


    def registrar_feedback_engine(self, musica_info, rating_value, internal_user_id):
        if not internal_user_id: 
            return False
        
        cursor = self.conn.cursor()
        try:
            
            track_id = musica_info.get('spotify_id') or musica_info.get('youtube_id')

            cursor.execute(
                "INSERT INTO historico_reproducao (usuario_id, musica_id, artista_id, rating) VALUES (?, ?, ?, ?)",
                (internal_user_id, track_id, musica_info.get('artista_id'), rating_value)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[Engine] Erro ao registar feedback no BD: {e}")
            return False
     
    def registrar_feedback_playlist_engine(self, lista_de_musicas, rating_value, internal_user_id):
        if not internal_user_id: return False
        sucessos = 0
        for musica in lista_de_musicas:
            if self.registrar_feedback_engine(musica, rating_value, internal_user_id):
                sucessos += 1
        print(f"[Engine] Feedback em lote registado para {sucessos} de {len(lista_de_musicas)} músicas.")
        return sucessos > 0

