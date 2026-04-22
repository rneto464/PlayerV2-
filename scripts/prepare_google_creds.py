#!/usr/bin/env python3
"""
Script helper para preparar as credenciais do Google para uso na Vercel.
Converte o arquivo google-credentials.json em uma string JSON de uma linha.
"""
import json
import os
import sys

def main():
    # Caminho do arquivo de credenciais
    creds_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'google-credentials.json')
    
    if not os.path.exists(creds_file):
        print(f"ERRO: Arquivo não encontrado: {creds_file}")
        print("Certifique-se de que o arquivo google-credentials.json existe na raiz do projeto.")
        sys.exit(1)
    
    try:
        # Lê o arquivo JSON
        with open(creds_file, 'r') as f:
            creds_data = json.load(f)
        
        # Converte para string JSON de uma linha
        json_string = json.dumps(creds_data)
        
        print("=" * 80)
        print("CREDENCIAIS DO GOOGLE PRONTAS PARA COPIAR:")
        print("=" * 80)
        print()
        print("1. Acesse o Dashboard da Vercel: https://vercel.com/dashboard")
        print("2. Vá para Settings > Environment Variables")
        print("3. Adicione uma nova variável:")
        print("   Nome: GOOGLE_CREDENTIALS_JSON")
        print("   Valor: (cole o JSON abaixo)")
        print()
        print("-" * 80)
        print(json_string)
        print("-" * 80)
        print()
        print("4. Selecione os ambientes (Production, Preview, Development)")
        print("5. Clique em Save")
        print("6. Faça um novo deploy")
        print()
        print("=" * 80)
        
        # Também salva em um arquivo para facilitar
        output_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'google-credentials-oneline.txt')
        with open(output_file, 'w') as f:
            f.write(json_string)
        
        print(f"\n✓ JSON também salvo em: {output_file}")
        print("  (Você pode copiar diretamente deste arquivo)")
        
    except json.JSONDecodeError as e:
        print(f"ERRO: O arquivo JSON está inválido: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

