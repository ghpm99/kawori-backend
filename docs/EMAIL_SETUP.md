# Configuração de Email para Notificações de Pagamento

## Visão Geral

Este documento descreve como configurar o envio de notificações de pagamento por email utilizando uma conta Gmail.

## Pré-requisitos

1. Conta Gmail ativa
2. Senha de aplicativo do Google (não usa senha normal da conta)

## Passos para Configuração

### 1. Habilitar Senha de Aplicativo no Google

1. Acesse sua conta Google: https://myaccount.google.com/
2. Vá para "Segurança"
3. Ative a "Verificação em duas etapas" (se ainda não estiver ativa)
4. Procure por "Senhas de aplicativos"
5. Clique em "Gerenciar senhas de aplicativos"
6. Selecione "Outro (nome personalizado)"
7. Dê um nome como "Kawori Financeiro"
8. Copie a senha gerada (16 caracteres)

### 2. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com base no `.env.example`:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas credenciais:

```env
EMAIL_HOST_USER=seu_email@gmail.com
EMAIL_HOST_PASSWORD=sua_senha_de_app_gerada
NOTIFICATION_EMAIL=email@destinatario.com
```

### 3. Instalar Dependências

As dependências necessárias já estão incluídas no Django, mas certifique-se de que o projeto está atualizado:

```bash
pip install -r requirements.txt
```

## Como Usar

### Executar Manualmente

```bash
python manage.py cron_payment_email
```

### Configurar Cron Job

Para executar automaticamente todos os dias às 9h:

```bash
# Editar crontab
crontab -e

# Adicionar a linha
0 9 * * * /path/to/venv/bin/python /path/to/project/manage.py cron_payment_email
```

## Template de Email

O template HTML está localizado em:
- `templates/payment_email_template.html`

Você pode personalizar o layout, cores e conteúdo conforme necessário.

## Configurações Adicionais

### Para Produção

No arquivo `kawori/settings/production.py`, você pode sobrescrever as configurações:

```python
EMAIL_HOST = 'smtp.seuprovedor.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
```

### Para Desenvolvimento

No arquivo `kawori/settings/development.py`, você pode usar o console para testes:

```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

## Segurança

- **Nunca** commitar o arquivo `.env` no versionamento
- Use sempre senhas de aplicativo, não a senha da sua conta Gmail
- Considere usar variáveis de ambiente do servidor em produção

## Testes

Para testar o envio de email:

```python
from django.core.mail import send_mail
send_mail(
    'Test Subject',
    'Test message',
    'from@example.com',
    ['to@example.com'],
    fail_silently=False,
)
```

## Solução de Problemas

### Erro: "SMTPAuthenticationError 534"

- Verifique se a verificação em duas etapas está ativa
- Use uma senha de aplicativo, não a senha normal

### Erro: "SMTPServerDisconnected"

- Verifique as configurações de firewall
- Confirme se EMAIL_PORT está correto (587 para TLS)

### Emails não chegando

- Verifique a pasta de spam
- Confirme o email destinatário em NOTIFICATION_EMAIL
- Verifique logs do aplicativo para erros
