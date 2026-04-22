# Nome do ficheiro: app/youtube_auth_manager.py
import os
from google_auth_oauthlib.flow import Flow

# Define o caminho para o ficheiro de credenciais descarregado da Google Cloud Console
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRETS_FILE = os.path.join(ROOT_DIR, 'youtube-credentials.json')

# Escopos necessários para ver e gerir playlists do YouTube do utilizador
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

class YouTubeAuthManager:
    """Gere o fluxo de autenticação OAuth 2.0 para a API do YouTube."""

    def get_flow(self):
        """
        Cria e retorna uma instância do Flow de autenticação da Google,
        configurado com as nossas credenciais e escopos.
        """
        if not os.path.exists(CLIENT_SECRETS_FILE):
            raise FileNotFoundError(
                f"Ficheiro de credenciais do YouTube não encontrado: {CLIENT_SECRETS_FILE}. "
                "Faça o download do ficheiro OAuth 2.0 na Google Cloud Console e coloque-o na raiz do projeto."
            )
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES
        )
        # Este URI de redirecionamento DEVE ser o mesmo que foi configurado
        # na Google Cloud Console nas suas credenciais.
        flow.redirect_uri = 'http://127.0.0.1:5000/callback/youtube'
        return flow

    def get_auth_url(self):
        """
        Gera a URL de autorização para a qual o utilizador será redirecionado
        para dar o seu consentimento.
        """
        flow = self.get_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        # Preserve code_verifier if PKCE was used
        code_verifier = getattr(flow, 'code_verifier', None)
        return authorization_url, state, code_verifier

    def get_token_from_code(self, authorization_response_url, state, code_verifier=None):
        """
        Recebe a resposta do servidor da Google e troca o código por um token de acesso.
        """
        flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
        flow.redirect_uri = 'http://127.0.0.1:5000/callback/youtube'
        fetch_kwargs = {'authorization_response': authorization_response_url}
        if code_verifier:
            fetch_kwargs['code_verifier'] = code_verifier
        flow.fetch_token(**fetch_kwargs)
        
        credentials = flow.credentials
        # Converte as credenciais para um formato de dicionário que pode ser
        # facilmente guardado na sessão do Flask.
        return {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
