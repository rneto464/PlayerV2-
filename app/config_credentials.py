# Nome do ficheiro: config/config_credentials.py
# Guarde todas as suas credenciais aqui.
# NUNCA partilhe este ficheiro publicamente se contiver chaves reais.

# ===================================================
# Credenciais do Spotify
# Obtidas no seu Spotify Developer Dashboard
# ===================================================
SPOTIPY_CLIENT_ID = 'e95951da1ae3474eb866710533b33045'
SPOTIPY_CLIENT_SECRET = '486b958bb0c24b6f95f2fd969978e381'

# O URI de redirecionamento que você configurou no seu painel do Spotify
SPOTIFY_REDIRECT_URI = 'http://127.0.0.1:5000/callback/spotify'

# As permissões que a sua aplicação irá pedir ao utilizador
SPOTIFY_SCOPES = 'playlist-modify-public user-read-private user-read-email'

# ===================================================
# Credenciais da Google
# ===================================================

# Chave de API do Google Gemini (obtida no Google AI Studio)
# Usada para gerar os prompts de recomendação
GEMINI_API_KEY = 'AIzaSyBzXO3GxuQ2PvsPuOqgVYnuxvDp5iz0MD8'

# Chave de API do YouTube (obtida na Google Cloud Console)
# Usada para fazer buscas públicas de músicas no YouTube
YOUTUBE_API_KEY = 'AIzaSyDYsVgjgtBEuK7mAlRiuLrirnKE_eMszdk'
