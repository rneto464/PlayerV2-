# Nome do ficheiro: app/services/youtube_service.py
import yt_dlp
from .base_service import MusicService

class YouTubeMusicService(MusicService):
    """A implementação do MusicService para a plataforma YouTube Music."""

    def __init__(self, developer_key=None):
        """
        Inicializa o serviço. O yt-dlp não precisa de chave para funcionar.
        :param developer_key: A chave de API da Google Cloud Console. (não utilizada aqui)
        """
        pass  

    def _map_youtube_to_standard_format(self, entry):
        """Converte um item de vídeo do YouTube para o nosso formato padrão."""
        video_id = entry.get('id')
        
        return {
            'titulo': entry.get('title'),
            'artista': entry.get('uploader'),
            'artista_id': entry.get('uploader_id'),
            'preview_url': f"https://www.youtube.com/watch?v={video_id}",
            'youtube_id': video_id, 
            'album_cover_url': entry.get('thumbnails', [{}])[-1].get('url') if entry.get('thumbnails') else None,
            'service': 'youtube'
        }

    def search_tracks(self, query, limit=25, market='BR'):
        """Busca vídeos de música no YouTube."""
        try:
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'extract_flat': True,
                'default_search': f'ytsearch{limit}',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(query + " music", download=False)
                entries = result['entries'] if 'entries' in result else []
                tracks = [self._map_youtube_to_standard_format(entry) for entry in entries]
                return tracks
        except Exception as e:
            print(f"[YouTubeService] Erro na busca yt-dlp: {e}")
            return None

    def get_recommendations_by_artists(self, artist_ids, limit=25, market='BR'):
        """Obtém recomendações do YouTube com base em artistas (canais)."""
        if not artist_ids:
            return []
        channel_id = artist_ids[0]
        try:
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'extract_flat': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                url = f"https://www.youtube.com/channel/{channel_id}/videos"
                result = ydl.extract_info(url, download=False)
                entries = result['entries'] if 'entries' in result else []
                tracks = [self._map_youtube_to_standard_format(entry) for entry in entries[:limit]]
                return tracks
        except Exception as e:
            print(f"[YouTubeService] Erro nas recomendações yt-dlp: {e}")
            return None

    def search_artists(self, query, limit=1):
        """Busca por canais (artistas) no YouTube."""
        try:
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'extract_flat': True,
                'default_search': f'ytsearch{limit}',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(query, download=False)
                entries = result['entries'] if 'entries' in result else []
                artists = [{'id': entry.get('id'), 'name': entry.get('title')} for entry in entries if entry.get('ie_key') == 'YoutubeChannel']
                return artists
        except Exception as e:
            print(f"[YouTubeService] Erro na busca de artistas yt-dlp: {e}")
            return []
