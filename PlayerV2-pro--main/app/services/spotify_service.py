# Nome do ficheiro: app/services/spotify_service.py
from .base_service import MusicService

class SpotifyService(MusicService):
    """A implementação do MusicService para a plataforma Spotify."""

    def __init__(self, spotify_client):
        self.sp_app = spotify_client

    def search_tracks(self, query, limit=25, market='BR'):
        """Busca faixas no Spotify."""
        try:
            results = self.sp_app.search(q=query, limit=limit, type='track', market=market)
            return results.get('tracks', {}).get('items', [])
        except Exception as e:
            print(f"[SpotifyService] Erro na busca: {e}"); return None

    def get_recommendations_by_artists(self, artist_ids, limit=25, market='BR'):
        """Obtém recomendações do Spotify com base em artistas."""
        try:
            # A biblioteca spotipy lida com a formatação da lista de IDs.
            results = self.sp_app.recommendations(seed_artists=artist_ids, limit=limit, market=market)
            return results.get('tracks', [])
        except Exception as e:
            print(f"[SpotifyService] Erro nas recomendações por artista: {e}"); return None
    
    def search_artists(self, query, limit=1):
        """Busca por artistas no Spotify."""
        try:
            results = self.sp_app.search(q=query, type='artist', limit=limit)
            return results.get('artists', {}).get('items', [])
        except Exception as e:
            print(f"[SpotifyService] Erro na busca de artistas: {e}"); return []

    def create_playlist(self, user_client, playlist_name, tracks, description="Playlist criada por PlayerV2 IA"):
        """
        Cria uma playlist na conta do utilizador do Spotify.
        O ID do utilizador é obtido diretamente do cliente autenticado para maior fiabilidade.
        """
        if not tracks:
            raise ValueError("A lista de músicas não pode estar vazia.")

        try:
            # Obtém o ID do utilizador diretamente do cliente autenticado.
            user_id = user_client.me()['id']
            
            nova_playlist = user_client.user_playlist_create(
                user=user_id,
                name=playlist_name,
                public=True,
                description=description
            )
            playlist_id = nova_playlist['id']
            
            track_uris = [f"spotify:track:{track['spotify_id']}" for track in tracks]
            if track_uris:
                for i in range(0, len(track_uris), 100):
                    user_client.playlist_add_items(playlist_id, track_uris[i:i + 100])
            
            return nova_playlist

        except Exception as e:
            print(f"[SpotifyService] Erro ao criar playlist: {e}")
            raise
