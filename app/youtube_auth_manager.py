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
        # 'access_type=offline' permite que a nossa aplicação obtenha um refresh_token,
        # o que nos permite renovar o acesso sem pedir ao utilizador para fazer login novamente.
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        return authorization_url, state

    def get_token_from_code(self, authorization_response_url, state):
        """
        Recebe a resposta do servidor da Google, valida o 'state' para segurança
        e troca o código de autorização por um token de acesso.
        """
        flow = self.get_flow()
        # Nota: numa aplicação em produção, você deveria validar se o 'state' recebido
        # corresponde ao 'state' que enviou.
        flow.fetch_token(authorization_response=authorization_response_url)
        
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
