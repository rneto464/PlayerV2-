#!/usr/bin/env python3
"""
Script de diagnóstico para identificar problemas com o YouTube
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yt_dlp

def testar_yt_dlp():
    """Testa se o yt-dlp consegue buscar vídeos"""
    print("=" * 60)
    print("TESTE 1: Verificação do yt-dlp")
    print("=" * 60)
    
    try:
        query = "beach music"
        ydl_opts = {
            'quiet': False,  # Mostra logs para debug
            'skip_download': True,
            'extract_flat': True,
            'default_search': 'ytsearch5',
            'noplaylist': True,
        }
        
        print(f"Buscando: '{query}'")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(query, download=False)
            
            if isinstance(result, list):
                entries = result
            else:
                entries = result.get('entries', [])
            
            print(f"\nResultado: {len(entries)} entradas encontradas")
            
            if entries:
                print("\nPrimeiras 3 entradas:")
                for i, entry in enumerate(entries[:3], 1):
                    print(f"\n{i}. Tipo: {type(entry)}")
                    if isinstance(entry, dict):
                        print(f"   ID: {entry.get('id', 'N/A')}")
                        print(f"   Título: {entry.get('title', entry.get('fulltitle', 'N/A'))}")
                        print(f"   URL: {entry.get('url', entry.get('webpage_url', 'N/A'))}")
                        print(f"   Canal: {entry.get('channel', entry.get('uploader', 'N/A'))}")
                    else:
                        print(f"   Valor: {entry}")
                return True
            else:
                print("ERRO: Nenhuma entrada encontrada!")
                print(f"Resultado completo: {result}")
                return False
                
    except Exception as e:
        print(f"ERRO ao testar yt-dlp: {e}")
        import traceback
        traceback.print_exc()
        return False

def testar_busca_simples():
    """Testa uma busca mais simples"""
    print("\n" + "=" * 60)
    print("TESTE 2: Busca simples sem extract_flat")
    print("=" * 60)
    
    try:
        query = "tropical house music"
        ydl_opts = {
            'quiet': False,
            'skip_download': True,
            'extract_flat': False,  # Tenta obter mais informações
            'default_search': 'ytsearch3',
            'noplaylist': True,
        }
        
        print(f"Buscando: '{query}'")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(query, download=False)
            
            if isinstance(result, list):
                entries = result
            else:
                entries = result.get('entries', [])
            
            print(f"\nResultado: {len(entries)} entradas encontradas")
            
            if entries:
                print("\nPrimeira entrada completa:")
                entry = entries[0]
                if isinstance(entry, dict):
                    for key, value in list(entry.items())[:10]:
                        print(f"   {key}: {value}")
                return True
            else:
                print("ERRO: Nenhuma entrada encontrada!")
                return False
                
    except Exception as e:
        print(f"ERRO ao testar busca simples: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("DIAGNÓSTICO DO YOUTUBE SERVICE")
    print("=" * 60 + "\n")
    
    resultado1 = testar_yt_dlp()
    resultado2 = testar_busca_simples()
    
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Teste 1 (extract_flat=True): {'✓ PASSOU' if resultado1 else '✗ FALHOU'}")
    print(f"Teste 2 (extract_flat=False): {'✓ PASSOU' if resultado2 else '✗ FALHOU'}")
    
    if not resultado1 and not resultado2:
        print("\n⚠ PROBLEMA CRÍTICO: yt-dlp não está retornando resultados!")
        print("Possíveis causas:")
        print("1. Problema de conexão com internet")
        print("2. YouTube bloqueou o acesso")
        print("3. yt-dlp precisa ser atualizado")
        print("\nTente atualizar: pip install --upgrade yt-dlp")
    elif not resultado1:
        print("\n⚠ Problema com extract_flat=True, mas extract_flat=False funciona")
        print("Solução: Usar extract_flat=False no código")
    else:
        print("\n✓ yt-dlp está funcionando corretamente!")
        print("O problema pode estar no processamento dos dados retornados.")

