import yt_dlp
import json

query = "Lana Del Rey - Video Games"

ydl_opts = {
    'quiet': True,
    'skip_download': True,
    'extract_flat': True,
    'default_search': 'ytsearch1',
}

print(f"--- INICIANDO TESTE ISOLADO DO YT-DLP ---")
print(f"Buscando por: '{query}'")

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(query + " music", download=False)
        print("\n--- TESTE CONCLUÍDO COM SUCESSO ---")
        print(json.dumps(result, indent=2))

except Exception as e:
    print("\n--- O TESTE FALHOU ---")
    print("Ocorreu um erro direto na biblioteca yt-dlp:")
    print(e)