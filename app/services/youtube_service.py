# Nome do ficheiro: app/services/youtube_service.py
import yt_dlp
import yt_dlp.utils
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest
from .base_service import MusicService

class YouTubeMusicService(MusicService):
    """A implementação do MusicService para a plataforma YouTube Music."""

    def __init__(self, developer_key=None):
        """
        Inicializa o serviço. Agora usa yt-dlp para buscas, que não requer chave de API.
        A chave de API ainda é usada para criar playlists (requer autenticação OAuth).
        :param developer_key: Opcional - chave de API da Google Cloud Console (para criar playlists).
        """
        self.developer_key = developer_key
        # yt-dlp não requer inicialização especial

    def _map_youtube_to_standard_format(self, entry):
        """Converte um item de vídeo do YouTube (yt-dlp ou API) para o nosso formato padrão."""
        if not isinstance(entry, dict):
            print(f"[YouTubeService] [Map] ⚠ Entrada não é dict: {type(entry)}")
            return None
            
        # Formato yt-dlp (com extract_flat=False ou True)
        # Tenta obter o ID do vídeo de diferentes formas
        video_id = entry.get('id') or entry.get('video_id') or entry.get('display_id')
        
        # Se não tem ID direto, tenta extrair da URL
        if not video_id:
            url = entry.get('url', entry.get('webpage_url', entry.get('original_url', '')))
            if 'watch?v=' in url:
                video_id = url.split('watch?v=')[-1].split('&')[0].split('/')[0]
        
        if not video_id:
            print(f"[YouTubeService] [Map] ⚠ Não foi possível extrair video_id. Chaves disponíveis: {list(entry.keys())[:10]}")
            return None
        
        # Obtém título
        title = entry.get('title', entry.get('fulltitle', entry.get('name', 'Sem título')))
        if not title or title == 'Sem título':
            print(f"[YouTubeService] [Map] AVISO: Título não encontrado na entrada")
        
        # Obtém artista/canal - yt-dlp usa 'channel' quando extract_flat=False
        artist = (entry.get('channel') or entry.get('uploader') or 
                 entry.get('channel_name') or entry.get('creator') or 
                 entry.get('channelTitle', 'Desconhecido'))
        
        # Obtém thumbnail
        thumbnail = entry.get('thumbnail', '')
        if not thumbnail and isinstance(entry.get('thumbnails'), list) and len(entry.get('thumbnails', [])) > 0:
            thumbnail = entry.get('thumbnails', [{}])[0].get('url', '')
        
        # Obtém URL
        video_url = (entry.get('url') or entry.get('webpage_url') or 
                    entry.get('original_url') or f"https://www.youtube.com/watch?v={video_id}")
        
        track = {
            'titulo': title,
            'artista': artist,
            'artista_id': entry.get('channel_id', entry.get('uploader_id', '')),
            'preview_url': video_url if video_url.startswith('http') else f"https://www.youtube.com/watch?v={video_id}",
            'spotify_id': video_id,
            'album_cover_url': thumbnail,
            'service_name': 'youtube',
            'id': video_id  # Adiciona também 'id' para compatibilidade
        }
        
        print(f"[YouTubeService] [Map] Mapeado: {title[:50]} - {artist[:30]} (ID: {video_id})")
        return track

    def search_tracks(self, query, limit=25, market='BR'):
        """Busca vídeos de música no YouTube usando yt-dlp."""
        print(f"[YouTubeService] ===== INÍCIO DA BUSCA =====")
        print(f"[YouTubeService] Query recebida: '{query}'")
        print(f"[YouTubeService] Limite: {limit}, Market: {market}")
        
        try:
            # Prepara a query de busca - se já contém "music", não adiciona novamente
            search_query = query
            if "music" not in query.lower() and " - " not in query:
                search_query = f"{query} music"
                print(f"[YouTubeService] Query ajustada: '{search_query}'")
            else:
                print(f"[YouTubeService] Query mantida como está: '{search_query}'")
            
            # Configurações do yt-dlp para busca
            # IMPORTANTE: extract_flat=True não funciona corretamente, precisa ser False
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'extract_flat': False,  # PRECISA ser False para funcionar!
                'default_search': f'ytsearch{limit}',
                'noplaylist': True,
                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},  # Evita problemas de JS
            }
            print(f"[YouTubeService] Configurações yt-dlp: extract_flat=False, default_search=ytsearch{limit}")
            
            tracks = []
            print(f"[YouTubeService] Inicializando yt-dlp...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"[YouTubeService] Chamando extract_info com: '{search_query}'")
                result = ydl.extract_info(search_query, download=False)
                print(f"[YouTubeService] ✓ extract_info concluído. Tipo do resultado: {type(result)}")
                
                # Com extract_flat=False, o resultado é um dict com 'entries' contendo os vídeos
                if isinstance(result, dict):
                    entries = result.get('entries', [])
                    # Se entries está vazio mas result tem '_type': 'playlist', pode ser que não processou
                    if not entries and result.get('_type') == 'playlist':
                        print(f"[YouTubeService] AVISO: Playlist vazia ou não processada")
                elif isinstance(result, list):
                    entries = result
                else:
                    entries = []
                
                if not entries:
                    print(f"[YouTubeService] ❌ Nenhum resultado encontrado para: {search_query}")
                    print(f"[YouTubeService] Tipo do resultado: {type(result)}")
                    if isinstance(result, dict):
                        print(f"[YouTubeService] Chaves do resultado: {list(result.keys())[:10]}")
                        print(f"[YouTubeService] Conteúdo completo (primeiros 500 chars): {str(result)[:500]}")
                    elif isinstance(result, list):
                        print(f"[YouTubeService] Resultado é uma lista com {len(result)} itens")
                    return []
                
                print(f"[YouTubeService] ✓ Encontradas {len(entries)} entradas brutas")
                
                # Processa cada entrada
                for idx, entry in enumerate(entries[:limit]):
                    if not entry:
                        print(f"[YouTubeService] Entrada {idx} está vazia")
                        continue
                    
                    try:
                        # Extrai informações básicas
                        if isinstance(entry, dict):
                            # Com extract_flat=True, temos informações limitadas mas suficientes
                            video_id = entry.get('id')
                            if not video_id:
                                # Tenta extrair da URL
                                url = entry.get('url', entry.get('webpage_url', ''))
                                if 'watch?v=' in url:
                                    video_id = url.split('watch?v=')[-1].split('&')[0].split('/')[0]
                            
                            if video_id and len(video_id) >= 10:  # IDs válidos têm pelo menos 10-11 caracteres
                                print(f"[YouTubeService] Processando entrada {idx}: ID={video_id}")
                                track = self._map_youtube_to_standard_format(entry)
                                if track:
                                    print(f"[YouTubeService] Track mapeado: titulo={track.get('titulo')}, artista={track.get('artista')}, spotify_id={track.get('spotify_id')}")
                                    if track.get('spotify_id'):
                                        tracks.append(track)
                                        print(f"[YouTubeService] ✓ Adicionado: {track.get('titulo', 'N/A')} - {track.get('artista', 'N/A')}")
                                    else:
                                        print(f"[YouTubeService] ⚠ Track sem spotify_id: {track}")
                                else:
                                    print(f"[YouTubeService] ⚠ _map_youtube_to_standard_format retornou None para entrada {idx}")
                            else:
                                print(f"[YouTubeService] ⚠ Entrada {idx} não tem ID válido. video_id={video_id}, entry keys: {list(entry.keys())[:10] if isinstance(entry, dict) else 'N/A'}")
                        elif isinstance(entry, str):
                            # Se for uma URL string
                            if 'watch?v=' in entry:
                                video_id = entry.split('watch?v=')[-1].split('&')[0]
                                if len(video_id) >= 10:
                                    tracks.append({
                                        'titulo': 'Vídeo do YouTube',
                                        'artista': 'Desconhecido',
                                        'artista_id': '',
                                        'preview_url': f"https://www.youtube.com/watch?v={video_id}",
                                        'spotify_id': video_id,
                                        'album_cover_url': '',
                                        'service_name': 'youtube',
                                        'id': video_id
                                    })
                    except Exception as e:
                        print(f"[YouTubeService] Erro ao processar entrada {idx}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
            
            print(f"[YouTubeService] ===== RESULTADO FINAL =====")
            print(f"[YouTubeService] Total de faixas processadas: {len(tracks)}")
            if len(tracks) == 0:
                print(f"[YouTubeService] ❌ AVISO CRÍTICO: Nenhum resultado encontrado!")
                print(f"[YouTubeService] Query usada: {search_query}")
                print(f"[YouTubeService] Entradas brutas encontradas: {len(entries) if 'entries' in locals() else 0}")
            else:
                print(f"[YouTubeService] ✓ Sucesso! Primeiras 3 faixas:")
                for i, track in enumerate(tracks[:3], 1):
                    print(f"[YouTubeService]   {i}. {track.get('titulo', 'N/A')} - {track.get('artista', 'N/A')}")
            print(f"[YouTubeService] ===== FIM DA BUSCA =====")
            return tracks if tracks else []
            
        except yt_dlp.utils.DownloadError as e:
            print(f"[YouTubeService] Erro de download do yt-dlp: {e}")
            print(f"[YouTubeService] Detalhes: {str(e)}")
            # Fallback para API antiga se yt-dlp falhar
            if self.developer_key:
                try:
                    print("[YouTubeService] Tentando fallback com API oficial...")
                    return self._search_with_api(query, limit)
                except Exception as e2:
                    print(f"[YouTubeService] Fallback também falhou: {e2}")
            return []
        except Exception as e:
            print(f"[YouTubeService] Erro inesperado na busca com yt-dlp: {e}")
            import traceback
            traceback.print_exc()
            # Fallback para API antiga se yt-dlp falhar
            if self.developer_key:
                try:
                    print("[YouTubeService] Tentando fallback com API oficial...")
                    return self._search_with_api(query, limit)
                except Exception as e2:
                    print(f"[YouTubeService] Fallback também falhou: {e2}")
            return []
    
    def _search_with_api(self, query, limit):
        """Método de fallback usando a API oficial (se disponível)."""
        youtube_client = build('youtube', 'v3', developerKey=self.developer_key)
        search_query = query if " - " in query else query + " music"
        search_response = youtube_client.search().list(
            q=search_query,
            part='snippet',
            maxResults=limit,
            type='video',
            videoCategoryId='10'
        ).execute()
        items = search_response.get('items', [])
        return [self._map_youtube_to_standard_format(item) for item in items]

    def get_recommendations_by_artists(self, artist_ids, limit=25, market='BR'):
        """Obtém recomendações do YouTube com base em artistas (canais)."""
        if not artist_ids: return []
        # Com yt-dlp, buscamos pelo nome do artista
        try:
            # Usa o primeiro artista ID como nome para busca
            artist_query = artist_ids[0] if isinstance(artist_ids[0], str) and not artist_ids[0].startswith('UC') else f"channel:{artist_ids[0]}"
            return self.search_tracks(artist_query, limit=limit, market=market)
        except Exception as e:
            print(f"[YouTubeService] Erro nas recomendações: {e}")
            return []
    
    def search_artists(self, query, limit=1):
        """Busca por canais (artistas) no YouTube usando yt-dlp."""
        try:
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'extract_flat': True,
                'default_search': f'ytsearch{limit}',
            }
            
            artists = []
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(f"{query} artist", download=False)
                entries = result.get('entries', [])
                
                for entry in entries[:limit]:
                    if entry:
                        artists.append({
                            'id': entry.get('channel_id', entry.get('id', '')),
                            'name': entry.get('channel', entry.get('uploader', 'Desconhecido'))
                        })
            
            return artists
        except Exception as e:
            print(f"[YouTubeService] Erro na busca de artistas: {e}")
            return []

    # --- MÉTODO ATUALIZADO: O parâmetro 'user_id' foi removido ---
    def create_playlist(self, user_client, playlist_name, tracks, description="Playlist criada por PlayerV2 IA"):
        """
        Cria uma playlist no YouTube e adiciona os vídeos (músicas) em lote.
        :param user_client: Um cliente da API do YouTube autenticado para o utilizador.
        """
        if not tracks: raise ValueError("A lista de músicas não pode estar vazia.")
        
        try:
            # 1. Cria a playlist
            playlist_body = {
                'snippet': {'title': playlist_name, 'description': description},
                'status': {'privacyStatus': 'public'}
            }
            playlist_response = user_client.playlists().insert(part='snippet,status', body=playlist_body).execute()
            playlist_id = playlist_response['id']
            playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

            # 2. Adiciona vídeos em lote (batch) para ser mais eficiente
            def batch_callback(request_id, response, exception):
                if exception:
                    print(f"Erro ao adicionar item à playlist do YouTube no pedido {request_id}: {exception}")

            batch = user_client.new_batch_http_request(callback=batch_callback)

            for track in tracks:
                video_id = track.get('spotify_id')
                if video_id:
                    playlist_item_body = {
                        'snippet': {
                            'playlistId': playlist_id,
                            'resourceId': {'kind': 'youtube#video', 'videoId': video_id}
                        }
                    }
                    batch.add(user_client.playlistItems().insert(part='snippet', body=playlist_item_body))
            
            batch.execute()

            # 3. Retorna os detalhes, incluindo a URL
            return {'external_urls': {'youtube': playlist_url}, 'id': playlist_id}

        except Exception as e:
            print(f"[YouTubeService] Erro ao criar playlist no YouTube: {e}")
            raise
