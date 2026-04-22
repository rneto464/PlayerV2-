# Nome do ficheiro: app/recommendation_engine.py
import os
import re
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
        print(f"[Engine] ===== INÍCIO DA ANÁLISE DE IMAGEM =====")
        print(f"[Engine] Caminho do arquivo: {filepath}")
        print(f"[Engine] Arquivo existe: {os.path.exists(filepath) if filepath else False}")
        
        if not self.vision_client:
            print("[Engine] ❌ ERRO: Cliente Google Vision não inicializado.")
            return None, None
        
        try:
            print("[Engine] Abrindo arquivo de imagem...")
            with open(filepath, 'rb') as f:
                content = f.read()
            print(f"[Engine] ✓ Arquivo lido com sucesso. Tamanho: {len(content)} bytes")
            
            tags_coletadas = set()
            
            print("[Engine] --- ETAPA 1: Análise com Vision API ---")
            try:
                response_web = self.vision_client.web_detection(image=vision.Image(content=content))
                if response_web.web_detection.web_entities:
                    print(f"[Engine] ✓ Vision API encontrou {len(response_web.web_detection.web_entities)} entidades")
                    for entity in response_web.web_detection.web_entities[:5]:
                        tags_coletadas.add(entity.description.lower())
                        print(f"[Engine]   - Tag Vision: {entity.description}")
                else:
                    print("[Engine] ⚠ Vision API não retornou entidades")
            except Exception as e:
                print(f"[Engine] ❌ ERRO na Vision API: {e}")
                import traceback
                traceback.print_exc()
            
            print("[Engine] --- ETAPA 2: Análise de emoção com Gemini ---")
            emotional_tags, playlist_title = self._analisar_emocao_e_titulo_com_ia(content)
            if emotional_tags:
                print(f"[Engine] ✓ Gemini retornou {len(emotional_tags)} tags de emoção")
                tags_coletadas.update(emotional_tags)
            else:
                print("[Engine] ⚠ Gemini não retornou tags de emoção")

            if not tags_coletadas:
                print("[Engine] ❌ ERRO: Nenhuma tag coletada de nenhuma fonte!")
                return None, None
                
            final_tags = list(tags_coletadas)
            print(f"[Engine] ✓ Tags Finais Combinadas ({len(final_tags)} tags): {final_tags}")
            print(f"[Engine] ✓ Título da playlist: {playlist_title}")
            print(f"[Engine] ===== FIM DA ANÁLISE DE IMAGEM =====")
            return final_tags, playlist_title

        except FileNotFoundError as e:
            print(f"[Engine] ❌ ERRO: Arquivo não encontrado: {e}")
            return None, None
        except Exception as e:
            print(f"[Engine] ❌ ERRO ao analisar imagem: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def _analisar_emocao_e_titulo_com_ia(self, image_content):
        """Usa o Gemini (multimodal) para obter tags de emoção e um título para a playlist."""
        print(f"[Engine] [Gemini] Verificando chave API...")
        if not self.gemini_api_key:
            print("[Engine] [Gemini] ❌ ERRO: GEMINI_API_KEY não configurada!")
            return [], "Playlist Sugerida"
        print(f"[Engine] [Gemini] ✓ Chave API presente (primeiros 10 chars: {self.gemini_api_key[:10]}...)")
        
        print(f"[Engine] [Gemini] Codificando imagem em base64...")
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        print(f"[Engine] [Gemini] ✓ Imagem codificada. Tamanho base64: {len(image_base64)} chars")
        
        prompt = ("Analyze this image and return JSON: "
                  "{\"playlist_title\": \"Creative Title (3-5 words)\", "
                  "\"mood_tags\": [\"tag1\", \"tag2\", \"tag3\", \"tag4\", \"tag5\"]} "
                  "Focus on atmosphere and emotion.")
        
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.gemini_api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": image_base64}}]}]}
        
        print(f"[Engine] [Gemini] Enviando requisição para API...")
        try:
            response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=20)
            print(f"[Engine] [Gemini] Status HTTP: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            
            if result.get('candidates'):
                print(f"[Engine] [Gemini] ✓ Resposta recebida com {len(result.get('candidates', []))} candidatos")
                json_string = result['candidates'][0]['content']['parts'][0]['text'].replace('```json', '').replace('```', '').strip()
                print(f"[Engine] [Gemini] JSON extraído: {json_string[:200]}...")
                data = json.loads(json_string)
                emotional_tags = data.get("mood_tags", [])
                playlist_title = data.get("playlist_title", "Playlist Sugerida")
                print(f"[Engine] [Gemini] ✓ Título: {playlist_title}")
                print(f"[Engine] [Gemini] ✓ Tags: {emotional_tags}")
                return emotional_tags, playlist_title
            else:
                print(f"[Engine] [Gemini] ⚠ Resposta sem candidatos. Resultado: {result}")
                return [], "Playlist Sugerida"
        except requests.exceptions.HTTPError as e:
            print(f"[Engine] [Gemini] ❌ ERRO HTTP: {e}")
            print(f"[Engine] [Gemini] Resposta: {response.text if 'response' in locals() else 'N/A'}")
            return [], "Playlist Sugerida"
        except json.JSONDecodeError as e:
            print(f"[Engine] [Gemini] ❌ ERRO ao decodificar JSON: {e}")
            print(f"[Engine] [Gemini] Texto recebido: {result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'N/A')[:500]}")
            return [], "Playlist Sugerida"
        except Exception as e:
            print(f"[Engine] [Gemini] ❌ ERRO inesperado: {e}")
            import traceback
            traceback.print_exc()
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

    def _construir_query_anime(self, tags):
        if not tags:
            return None
        tags_normalizados = []
        for t in tags:
            if t is None:
                continue
            s = str(t).strip()
            if not s:
                continue
            tags_normalizados.append(s.lower())
        if not tags_normalizados:
            return None
        texto_tags = " ".join(tags_normalizados)
        
        # Lógica específica para Roxy Migurdia (Mushoku Tensei)
        # Detecção melhorada para pegar variações ou combinações de tags
        has_roxy = "roxy" in texto_tags
        has_migurdia = "migurdia" in texto_tags
        has_mushoku = "mushoku" in texto_tags or "tensei" in texto_tags
        
        if (has_roxy and has_migurdia) or (has_roxy and has_mushoku):
            # Retorna uma query mais ampla para encontrar melhores resultados (OST completa ou temas)
            return "Mushoku Tensei OST Best Collection"
            
        if "mushoku tensei" in texto_tags:
            return "Mushoku Tensei Soundtrack"
            
        anime_keywords = ["anime", "manga", "otaku", "isekai", "light novel", "animation", "cartoon"]
        if not any(k in texto_tags for k in anime_keywords):
            return None
            
        genericos = ["anime", "manga", "character", "girl", "boy", "wallpaper", "illustration", "art", "drawing"]
        candidatos = sorted(tags_normalizados, key=len, reverse=True)
        base = None
        for tag in candidatos:
            if any(g in tag for g in genericos):
                continue
            base = tag
            break
        if not base:
            # Se só tiver tags genéricas, usa "Anime OST" + emoção se possível
            return "Best Anime Soundtracks"
            
        return base + " anime soundtrack"

    def recomendar_musicas_por_tags(self, tags, market='BR', limit=25, is_redo=False):
        """Orquestra a recomendação com base no serviço de música ativo."""
        print(f"[Engine] ===== INÍCIO DA RECOMENDAÇÃO DE MÚSICAS =====")
        print(f"[Engine] Tags recebidas: {tags}")
        print(f"[Engine] Limite: {limit}, Market: {market}, is_redo: {is_redo}")
        
        if not self.music_service:
            print("[Engine] ❌ ERRO: Serviço de música não inicializado!")
            return None
        
        service_type = type(self.music_service).__name__
        print(f"[Engine] Tipo de serviço: {service_type}")
        
        if not tags:
            print("[Engine] ❌ ERRO: Nenhuma tag fornecida!")
            return []

        tracks = []
        # LÓGICA PARA O SPOTIFY
        if isinstance(self.music_service, SpotifyService):
            print("[Engine] --- Usando estratégia do Spotify ---")
            query_musical = self._gerar_prompt_musical_spotify(tags, is_redo)
            print(f"[Engine] Prompt gerado: {query_musical}")
            tracks = self.music_service.search_tracks(query=query_musical, limit=limit, market=market)
        
        # LÓGICA PARA O YOUTUBE - Agora funciona igual ao Spotify
        elif isinstance(self.music_service, YouTubeMusicService):
            print("[Engine] --- Usando estratégia do YouTube ---")
            query_musical = self._gerar_prompt_musical_youtube(tags, is_redo)
            print(f"[Engine] Prompt gerado para YouTube: {query_musical}")
            if not query_musical:
                print("[Engine] ❌ ERRO: Prompt vazio para YouTube!")
                return []
            
            print(f"[Engine] Chamando search_tracks do YouTube...")
            tracks = self.music_service.search_tracks(query=query_musical, limit=limit, market=market)
            print(f"[Engine] ✓ search_tracks retornou: {len(tracks) if tracks else 0} faixas (tipo: {type(tracks)})")
            
            if not tracks or len(tracks) == 0:
                print("[Engine] ⚠ AVISO: Nenhuma faixa retornada do YouTube!")
                print("[Engine] Tentando busca alternativa com tags diretas...")
                fallback_query = " ".join(tags[:3]) + " music"
                print(f"[Engine] Busca alternativa: {fallback_query}")
                tracks = self.music_service.search_tracks(query=fallback_query, limit=limit, market=market)
                print(f"[Engine] Resultado da busca alternativa: {len(tracks) if tracks else 0} faixas")
            
            if tracks:
                print(f"[Engine] Primeira faixa exemplo: {tracks[0] if tracks else 'N/A'}")
        else:
            print(f"[Engine] ❌ ERRO: Tipo de serviço desconhecido: {service_type}")

        if tracks is None:
            print("[Engine] ❌ ERRO: tracks é None!")
            return None
        
        print(f"[Engine] Processando {len(tracks)} faixas...")
        resultado = self._processar_faixas_api(tracks, limit)
        print(f"[Engine] ✓ Processamento concluído. Resultado final: {len(resultado) if resultado else 0} faixas")
        if resultado:
            print(f"[Engine] ===== AMOSTRA DO RESULTADO (primeiras 2 faixas) =====")
            print(json.dumps(resultado[:2], indent=2, ensure_ascii=False))
            print(f"[Engine] =======================================================")
        print(f"[Engine] ===== FIM DA RECOMENDAÇÃO DE MÚSICAS =====")
        return resultado
    

    def _gerar_prompt_musical_spotify(self, tags, is_redo=False):
        """Gera um prompt de busca criativo para o Spotify."""
        anime_query = self._construir_query_anime(tags)
        if anime_query and not is_redo:
            print(f"[Engine] [Prompt Spotify] Contexto de anime detectado, usando query direta: {anime_query}")
            return anime_query
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
    
    def _gerar_prompt_musical_youtube(self, tags, is_redo=False):
        """Gera um prompt de busca criativo para o YouTube (igual ao Spotify)."""
        print(f"[Engine] [Prompt YouTube] Gerando prompt para tags: {tags}")
        anime_query = self._construir_query_anime(tags)
        if anime_query and not is_redo:
            print(f"[Engine] [Prompt YouTube] Contexto de anime detectado, usando query direta: {anime_query}")
            return anime_query
        if not self.gemini_api_key:
            print("[Engine] [Prompt YouTube] ⚠ GEMINI_API_KEY não disponível, usando tags diretas")
            return " ".join(tags[:3]) + " music"
        
        redo_instruction = "Give me a COMPLETELY DIFFERENT and UNEXPECTED music prompt for these tags. Think outside the box." if is_redo else ""
        prompt = (f"Given these tags describing an image: {tags}. "
                f"{redo_instruction} "
                "Generate a short, creative prompt for a music playlist search on YouTube. "
                "Examples: 'upbeat indie pop for a sunny beach day', 'lo-fi chill beats for a rainy city night', 'tropical house music beach vibes'")
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.gemini_api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        print(f"[Engine] [Prompt YouTube] Enviando requisição ao Gemini...")
        try:
            response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
            print(f"[Engine] [Prompt YouTube] Status HTTP: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            if result.get('candidates'): 
                prompt_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                print(f"[Engine] [Prompt YouTube] ✓ Prompt recebido: {prompt_text}")
                if "music" not in prompt_text.lower():
                    prompt_text += " music"
                    print(f"[Engine] [Prompt YouTube] Adicionado 'music' ao prompt")
                return prompt_text
            print("[Engine] [Prompt YouTube] ⚠ Sem candidatos, usando fallback")
            return " ".join(tags[:3]) + " music"
        except Exception as e:
            print(f"[Engine] [Prompt YouTube] ❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            return " ".join(tags[:3]) + " music"

    # Palavras que indicam que um segmento após " - " é uma versão/variação da música
    _PALAVRAS_VERSAO = {
        'remix', 'remixed', 'extended', 'extension', 'live', 'acoustic',
        'instrumental', 'edit', 'edited', 'remastered', 'remaster',
        'deluxe', 'mix', 'version', 'ver', 'cover', 'reprise', 'interlude',
        'mashup', 'medley', 'radio', 'unplugged', 'stripped', 'demo',
        'session', 'sessions', 'orchestral', 'symphonic', 'club', 'dub',
        'bonus', 'ao vivo', 'vivo', 'rework', 'reworked', 'refix', 'flip',
        'cut', 'take', 'alternate', 'alternative', 'official', 'single',
        'nightcore', 'sped', 'slowed', 'reverb', 'lofi', 'lo-fi', 'pitched',
        'speed', 'trap', 'bootleg', 'tribute', 'karaoke'
    }
    _FEAT_SPLIT = re.compile(r'\s+(?:feat\.?|ft\.?|&|,)\s+', re.IGNORECASE)

    def _chave_dedup(self, titulo, artista):
        """Retorna chave normalizada (titulo_base, artista_principal) para deduplicação semântica.

        Estratégia: divide o título por ' - ' e descarta qualquer segmento que
        contenha pelo menos uma palavra de versão, independente da posição.
        Isso cobre casos como 'Song - Empire Of The Sun Remix' e 'Song - Extended Mix'.
        """
        t = (titulo or '').lower().strip()
        # Remove conteúdo entre parênteses/colchetes: (Radio Edit), [Remastered]…
        t = re.sub(r'\s*[\(\[].*?[\)\]]', '', t).strip()
        # Divide por ' - ' e descarta segmentos com palavras de versão
        partes = [p.strip() for p in t.split(' - ') if p.strip()]
        if len(partes) > 1:
            palavras_segmento = lambda seg: set(re.split(r'\W+', seg))
            for i in range(1, len(partes)):
                if palavras_segmento(partes[i]) & self._PALAVRAS_VERSAO:
                    t = partes[0]
                    break
        # Artista principal (antes de feat/ft/&/,)
        a = self._FEAT_SPLIT.split((artista or '').lower().strip())[0].strip()
        return (t, a)

    def _processar_faixas_api(self, tracks, limit=25):
        """Processa faixas garantindo unicidade por ID e por (título base, artista principal)."""
        musicas_processadas = []
        ids_vistos = set()
        chaves_vistas = set()
        palavras_instrumentais = ['instrumental', 'karaoke', 'backing track', 'versão instrumental', 'versao instrumental']

        def is_instrumental(nome, artista):
            texto = f"{nome} {artista}".lower()
            return any(p in texto for p in palavras_instrumentais)

        for item in tracks:
            if len(musicas_processadas) >= limit:
                break
            if not item:
                continue

            is_youtube_format = 'titulo' in item and 'artista' in item

            if is_youtube_format:
                track_id = item.get('spotify_id') or item.get('id')
                if not track_id:
                    continue
                titulo = item.get('titulo', 'Sem título')
                artista = item.get('artista', 'Desconhecido')

                if is_instrumental(titulo, artista):
                    continue
                if track_id in ids_vistos:
                    continue
                chave = self._chave_dedup(titulo, artista)
                if chave in chaves_vistas:
                    print(f"[Engine] Duplicata semantica ignorada: {titulo} - {artista}")
                    continue

                yt_duration = item.get('duration', '')
                if not yt_duration:
                    yt_dur_secs = item.get('duration_seconds') or item.get('duration_ms', 0) // 1000
                    if yt_dur_secs:
                        yt_duration = f"{yt_dur_secs // 60}:{yt_dur_secs % 60:02d}"
                    else:
                        yt_duration = "3:45"
                track_final = {
                    'titulo': titulo,
                    'artista': artista,
                    'artista_id': item.get('artista_id', ''),
                    'preview_url': item.get('preview_url', f"https://www.youtube.com/watch?v={track_id}"),
                    'spotify_id': track_id,
                    'album_cover_url': item.get('album_cover_url', ''),
                    'service_name': 'youtube',
                    'id': track_id,
                    'duration': yt_duration
                }
                musicas_processadas.append(track_final)
                ids_vistos.add(track_id)
                chaves_vistas.add(chave)

            else:
                # Unwrap playlist-style items: {added_at, track: {...}}
                track_data = item.get('track') if isinstance(item.get('track'), dict) else item
                if not track_data.get('artists') or not track_data.get('id'):
                    continue
                spotify_id = track_data.get('id')
                artists_data = track_data.get('artists', [])
                titulo = track_data.get('name', '')
                artista = artists_data[0].get('name', 'N/A') if artists_data else 'N/A'

                if is_instrumental(titulo, artista):
                    continue
                if spotify_id in ids_vistos:
                    continue
                chave = self._chave_dedup(titulo, artista)
                if chave in chaves_vistas:
                    print(f"[Engine] Duplicata semantica ignorada: {titulo} - {artista}")
                    continue

                album_images = track_data.get('album', {}).get('images', [])
                duration_ms = track_data.get('duration_ms', 0)
                if duration_ms:
                    minutos = duration_ms // 60000
                    segundos = (duration_ms % 60000) // 1000
                    duration_str = f"{minutos}:{segundos:02d}"
                else:
                    duration_str = "00:00"
                musica = {
                    'titulo': titulo,
                    'artista': artista,
                    'artista_id': artists_data[0].get('id') if artists_data else None,
                    'preview_url': track_data.get('preview_url'),
                    'spotify_id': spotify_id,
                    'album_cover_url': album_images[0]['url'] if album_images else None,
                    'service_name': 'spotify',
                    'duration': duration_str
                }
                musicas_processadas.append(musica)
                ids_vistos.add(spotify_id)
                chaves_vistas.add(chave)

        return musicas_processadas



    def registrar_feedback_engine(self, musica_info, rating_value, internal_user_id):
        if not internal_user_id: return False
        cursor = self.conn.cursor()
        try:
            # A query já usa 'usuario_id', que é o nosso ID interno
            cursor.execute("INSERT INTO historico_reproducao (usuario_id, musica_id, artista_id, rating) VALUES (?, ?, ?, ?)",
                           (internal_user_id, musica_info.get('spotify_id'), musica_info.get('artista_id'), rating_value))
            self.conn.commit(); return True
        except Exception as e:
            print(f"[Engine] Erro ao registar feedback no BD: {e}"); return False

    # --- CORREÇÃO AQUI: Renomeado o parâmetro para clareza ---
    def registrar_feedback_playlist_engine(self, lista_de_musicas, rating_value, internal_user_id):
        if not internal_user_id: return False
        sucessos = 0
        for musica in lista_de_musicas:
            if self.registrar_feedback_engine(musica, rating_value, internal_user_id):
                sucessos += 1
        print(f"[Engine] Feedback em lote registado para {sucessos} de {len(lista_de_musicas)} músicas.")
        return sucessos > 0

