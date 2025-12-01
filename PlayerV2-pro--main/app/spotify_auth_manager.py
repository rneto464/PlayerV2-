import os
import webbrowser
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials


# Importação corrigida (com ponto) para encontrar o ficheiro no mesmo pacote
from . import config_credentials as creds

class SpotifyAuthManager:
    SCOPES = "playlist-modify-public playlist-modify-private"
    REDIRECT_URI = "http://127.0.0.1:5000/callback/spotify" # A porta deve ser a do Flask
    CACHE_FILE_PREFIX = ".spotify_token_cache-"

    def __init__(self):
        if not creds or creds.SPOTIPY_CLIENT_ID == 'SEU_CLIENT_ID_AQUI':
            raise ValueError("Credenciais do Spotify não configuradas em 'app/config_credentials.py'")
        
        self.client_id = creds.SPOTIPY_CLIENT_ID
        self.client_secret = creds.SPOTIPY_CLIENT_SECRET
    
    def get_app_client(self):
        """Retorna um cliente Spotipy para buscas públicas (Client Credentials)."""
        try:
            auth_manager = SpotifyClientCredentials(client_id=self.client_id, client_secret=self.client_secret)
            sp = spotipy.Spotify(auth_manager=auth_manager)
            print("[Auth Manager] Autenticação da aplicação Spotify bem-sucedida.")
            return sp
        except Exception as e: 
            print(f"[Auth Manager] Falha na autenticação da aplicação: {e}")
            return None

    def get_oauth_manager(self, session):
        """Cria e retorna um objeto SpotifyOAuth, usando a sessão para o cache path."""
        cache_path = f"{self.CACHE_FILE_PREFIX}{session.get('user_id')}" if session.get('user_id') else None
        return SpotifyOAuth(client_id=self.client_id, client_secret=self.client_secret, redirect_uri=self.REDIRECT_URI, scope=self.SCOPES, cache_path=cache_path, show_dialog=True)
    
    def get_token_from_code(self, oauth_manager, code):
        """Troca o código de autorização por um token de acesso."""
        return oauth_manager.get_access_token(code, as_dict=True, check_cache=False)

    def get_user_client(self, token_info):
        """Cria um cliente Spotipy a partir das informações do token."""
        if not token_info: return None
        return spotipy.Spotify(auth=token_info['access_token'])

    def logout(self, user_id):
        """Faz logout do utilizador, apagando o seu ficheiro de cache."""
        if user_id:
            cache_file = f"{self.CACHE_FILE_PREFIX}{user_id}"
            if os.path.exists(cache_file): 
                os.remove(cache_file)
                print(f"[Auth Manager] Cache removido para {user_id}.")
                return True
        return False