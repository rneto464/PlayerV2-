# PlayerV2 - IA Music Discovery

Aplicação web para descobrir músicas através de análise de imagens usando IA.

## Estrutura do Projeto

```
PlayerV2-pro--main/
├── app/                    # Código principal da aplicação
│   ├── services/          # Serviços de música (Spotify, YouTube)
│   ├── templates/         # Templates HTML
│   └── ...
├── config/                 # Arquivos de configuração e credenciais
│   ├── config_credentials.py
│   ├── google-credentials.json
│   └── youtube-credentials.json
├── data/                   # Banco de dados e dados estáticos
│   ├── banco_musicas.db
│   └── spotify_genres.txt
├── tests/                  # Scripts de teste e diagnóstico
├── logs/                   # Arquivos de log
├── media/                  # Arquivos de mídia
├── scripts/                # Scripts utilitários
├── temp_uploads/           # Uploads temporários de imagens
├── requirements.txt        # Dependências Python
└── README.md              # Este arquivo
```

## Configuração

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. Configure as credenciais em `config/config_credentials.py`:
   - Spotify API credentials
   - Google Gemini API key
   - YouTube API key (opcional)

3. Coloque os arquivos de credenciais JSON em `config/`:
   - `google-credentials.json` (Google Vision API)
   - `youtube-credentials.json` (YouTube OAuth)

## Execução

```bash
python -m app.server
```

Ou use o script:
```bash
.\iniciar.bat
```

A aplicação estará disponível em `http://localhost:5000`

## Funcionalidades

- Análise de imagens com Google Vision API
- Geração de recomendações musicais com IA (Gemini)
- Integração com Spotify e YouTube
- Criação de playlists
- Comunidade de playlists

