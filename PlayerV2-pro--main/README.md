# PlayerV2 - IA Music Discovery

Aplicação de descoberta de música usando Inteligência Artificial que analisa imagens e gera playlists personalizadas.

## 📁 Estrutura do Projeto

```
PlayerV2-pro--main/
├── app/                    # Código principal da aplicação
│   ├── services/          # Serviços de música (Spotify, YouTube)
│   ├── templates/         # Templates HTML
│   ├── server.py          # Servidor Flask principal
│   └── ...
├── config/                 # Configurações e credenciais
│   ├── google-credentials.json
│   ├── youtube-credentials.json
│   └── config_credentials.py
├── data/                   # Banco de dados e dados estáticos
│   ├── banco_musicas.db
│   └── spotify_genres.txt
├── scripts/                # Scripts utilitários
│   └── setup_database.py
├── tests/                  # Testes e diagnósticos
│   ├── teste_youtube.py
│   └── diagnostico_youtube.py
├── temp_uploads/           # Uploads temporários de imagens
├── logs/                   # Logs da aplicação
├── requirements.txt        # Dependências Python
└── iniciar.bat            # Script de inicialização

```

## 🚀 Como Iniciar

### Método 1: Script de Inicialização (Recomendado)
Duplo clique em `iniciar.bat`

### Método 2: Terminal
```powershell
cd "C:\Users\WINDOWS\Downloads\PlayerV2-pro--main\PlayerV2-pro--main"
python -m app.server
```

### Método 3: Executar diretamente
```powershell
python app\server.py
```

## 📋 Requisitos

- Python 3.x
- Dependências instaladas: `pip install -r requirements.txt`

## ⚙️ Configuração

1. Coloque suas credenciais em `config/`:
   - `google-credentials.json` (Google Vision API)
   - `youtube-credentials.json` (YouTube OAuth)
   - Configure `config/config_credentials.py` com suas chaves de API

2. Execute o setup do banco de dados:
   ```powershell
   python scripts\setup_database.py
   ```

## 🌐 Acesso

Após iniciar, acesse: **http://localhost:5000**

## 🔧 Funcionalidades

- Análise de imagens com Google Vision API
- Geração de playlists com IA (Gemini)
- Integração com Spotify e YouTube
- Recomendações baseadas em ambiente/emoção
- Criação de playlists nas plataformas

## 📝 Notas

- As credenciais são sensíveis e não devem ser commitadas
- O banco de dados é criado automaticamente na primeira execução
- Uploads temporários são limpos automaticamente

