# Configuração das Credenciais do Google na Vercel

Este guia explica como configurar as credenciais do Google Cloud Vision API na Vercel.

## Opção 1: Usar GOOGLE_CREDENTIALS_JSON (Recomendado)

Esta é a forma mais simples e segura de configurar as credenciais na Vercel.

### Passos:

1. **Acesse o Dashboard da Vercel**
   - Vá para https://vercel.com/dashboard
   - Selecione seu projeto

2. **Vá para Settings > Environment Variables**

3. **Adicione uma nova variável de ambiente:**
   - **Nome:** `GOOGLE_CREDENTIALS_JSON`
   - **Valor:** Cole o conteúdo completo do arquivo `google-credentials.json` como uma única linha JSON
   
   **Importante:** O valor deve ser o JSON completo em uma única linha. Exemplo:
   ```json
   {"type":"service_account","project_id":"seu-projeto","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"..."}
   ```

4. **Selecione os ambientes** onde a variável deve estar disponível:
   - ✅ Production
   - ✅ Preview
   - ✅ Development

5. **Clique em "Save"**

6. **Faça um novo deploy** para aplicar as mudanças

## Opção 2: Usar GOOGLE_APPLICATION_CREDENTIALS

Se você preferir usar um caminho para o arquivo:

1. **Faça upload do arquivo `google-credentials.json`** para um local acessível
2. **Adicione a variável de ambiente:**
   - **Nome:** `GOOGLE_APPLICATION_CREDENTIALS`
   - **Valor:** Caminho completo para o arquivo (ex: `/tmp/google-credentials.json`)

## Como obter o arquivo google-credentials.json

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Vá para **IAM & Admin > Service Accounts**
3. Selecione ou crie uma service account
4. Vá para **Keys > Add Key > Create new key**
5. Escolha **JSON** como formato
6. Baixe o arquivo JSON gerado

## Verificação

Após configurar, faça um novo deploy e verifique os logs. Você deve ver:
```
Credenciais do Google carregadas a partir da variável de ambiente GOOGLE_CREDENTIALS_JSON
```

Em vez de:
```
AVISO: Credenciais do Google não encontradas. Algumas funcionalidades podem não funcionar.
```

## Segurança

⚠️ **IMPORTANTE:**
- Nunca commite o arquivo `google-credentials.json` no Git
- O arquivo já está no `.gitignore` para sua proteção
- Use variáveis de ambiente na Vercel para manter as credenciais seguras
- As credenciais são armazenadas de forma criptografada na Vercel

