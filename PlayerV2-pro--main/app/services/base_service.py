class MusicService:
    """
    Define os métodos que qualquer serviço de música deve implementar.
    """
    
    def search_tracks(self, query, limit, market):
        raise NotImplementedError("Este método deve ser implementado pela subclasse.")

    def get_recommendations_by_artists(self, artist_ids, limit, market):
        raise NotImplementedError("Este método deve ser implementado pela subclasse.")
    
    def search_artists(self, query, limit):
        raise NotImplementedError("Este método deve ser implementado pela subclasse.")

    def create_playlist(self, user_client, playlist_name, tracks, description):
        # O user_id foi removido, pois cada serviço irá obtê-lo do cliente.
        raise NotImplementedError("Este método deve ser implementado pela subclasse.")
