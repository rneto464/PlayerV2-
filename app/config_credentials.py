import os

SPOTIPY_CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID") or "e95951da1ae3474eb866710533b33045"
SPOTIPY_CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET") or "486b958bb0c24b6f95f2fd969978e381"

SPOTIFY_REDIRECT_URI = os.environ.get(
    "SPOTIFY_REDIRECT_URI",
    "http://127.0.0.1:5000/callback/spotify",
)

SPOTIFY_SCOPES = os.environ.get(
    "SPOTIFY_SCOPES",
    "playlist-modify-public user-read-private user-read-email",
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or "SUA_GEMINI_API_KEY_AQUI"

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY") or "SUA_YOUTUBE_API_KEY_AQUI"
