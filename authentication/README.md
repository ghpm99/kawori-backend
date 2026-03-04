# Authentication App

Documentacao das rotas do app `authentication` (prefixo global: `/auth/`).

## Visao geral

- Base path: `/auth/`
- Formato de entrada: JSON no corpo para rotas `POST` (exceto quando indicado).
- Autenticacao: JWT em cookie HTTP-only (`access_token` e `refresh_token`).
- Cookies definidos no login:
  - `access_token` (`SameSite=Strict`)
  - `refresh_token` (`SameSite=Lax`, `path=/auth/token/refresh/`)
  - `lifetimetoken` (expiracao do refresh, `SameSite=None`)
- Tokens de uso unico:
  - `password_reset`: expira em 30 minutos.
  - `email_verification`: expira em 24 horas.

## Endpoints

### 1) POST `/auth/token/`
Objetivo: autenticar usuario e criar cookies de sessao JWT.

Payload (JSON):
```json
{
  "username": "string",
  "password": "string"
}
```

Retornos:
- `200 OK`
```json
{
  "refresh_token_expiration": "2026-03-03T12:34:56+00:00"
}
```
- `400 Bad Request` (campos obrigatorios ausentes)
```json
{
  "errors": [
    {"username": "Este campo e obrigatorio"},
    {"password": "Este campo e obrigatorio"}
  ]
}
```
- `404 Not Found`
```json
{"msg": "Dados incorretos."}
```
- `403 Forbidden` (ramo existente no codigo quando usuario inativo apos autenticar)
```json
{"msg": "Este usuario nao esta ativo."}
```
- `405 Method Not Allowed` para metodos diferentes de `POST`.
- Observacao tecnica: JSON malformado gera excecao (sem tratamento local), podendo resultar em `500`.

---

### 2) GET `/auth/signout`
Objetivo: logout, removendo cookies de autenticacao.

Payload: sem body.

Retornos:
- `200 OK`
```json
{"msg": "Deslogou"}
```
- `405 Method Not Allowed` para metodos diferentes de `GET`.

---

### 3) POST `/auth/token/verify/`
Objetivo: validar cookie `access_token`.

Payload:
- Body: nao utilizado.
- Cookie obrigatorio: `access_token`.

Retornos:
- `200 OK`
```json
{"msg": "Token valido"}
```
- `400 Bad Request` (cookie ausente)
```json
{"msg": "Token nao encontrado"}
```
- `401 Unauthorized` (token invalido/expirado/tipo incorreto)
```json
{"error": "<detalhe do simplejwt>", "valid": false}
```
- `405 Method Not Allowed` para metodos diferentes de `POST`.

---

### 4) POST `/auth/token/refresh/`
Objetivo: validar `refresh_token` e emitir novo `access_token`.

Payload:
- Body: nao utilizado.
- Cookie obrigatorio: `refresh_token`.

Retornos:
- `200 OK`
```json
{"msg": "Token valido"}
```
- `403 Forbidden` (cookie ausente)
```json
{"msg": "Token nao encontrado"}
```
- `403 Forbidden` (refresh invalido/expirado/tipo incorreto)
```json
{"error": "<detalhe do simplejwt>", "valid": false}
```
- `405 Method Not Allowed` para metodos diferentes de `POST`.

---

### 5) POST `/auth/signup`
Objetivo: criar novo usuario, registrar grupos e iniciar verificacao de email.

Payload (JSON):
```json
{
  "username": "string",
  "password": "string",
  "email": "string",
  "name": "string",
  "last_name": "string"
}
```

Retornos:
- `200 OK`
```json
{"msg": "Usuario criado com sucesso!"}
```
- `400 Bad Request` (campo obrigatorio ausente)
```json
{"msg": "Todos os campos sao obrigatorios."}
```
- `400 Bad Request` (username duplicado)
```json
{"msg": "Usuario ja cadastrado"}
```
- `400 Bad Request` (email duplicado)
```json
{"msg": "E-mail ja cadastrado"}
```
- `405 Method Not Allowed` para metodos diferentes de `POST`.
- Observacao tecnica: JSON malformado gera excecao (sem tratamento local), podendo resultar em `500`.

Notas de comportamento:
- Cria `EmailVerification` com `is_verified=False`.
- Gera token `email_verification` e dispara envio de email de forma assincrona.
- Falhas no envio de email e em budget padrao nao bloqueiam o cadastro (retorno continua `200`).

---

### 6) GET `/auth/csrf/`
Objetivo: garantir geracao de cookie CSRF no cliente.

Payload: sem body.

Retornos:
- `200 OK`
```json
{"msg": "Token registrado"}
```

---

### 7) POST `/auth/password-reset/request/`
Objetivo: iniciar fluxo de redefinicao de senha por email (sem enumerar usuarios).

Payload (JSON):
```json
{
  "email": "usuario@dominio.com"
}
```

Retornos:
- `200 OK` (sempre mensagem generica para email existente/inexistente/inativo/rate limit por usuario)
```json
{"msg": "Se o e-mail estiver cadastrado, voce recebera as instrucoes em breve."}
```
- `400 Bad Request` (JSON invalido)
```json
{"msg": "Requisicao invalida."}
```
- `400 Bad Request` (email ausente/vazio)
```json
{"msg": "E-mail e obrigatorio."}
```
- `429 Too Many Requests` (rate limit por IP)
```json
{"msg": "Muitas tentativas. Tente novamente mais tarde."}
```
- `405 Method Not Allowed` para metodos diferentes de `POST`.

---

### 8) GET `/auth/password-reset/validate/`
Objetivo: validar se token de reset ainda esta ativo (frontend usa antes de abrir formulario de nova senha).

Payload:
- Query param obrigatorio: `token`
- Exemplo: `/auth/password-reset/validate/?token=<token>`

Retornos:
- `200 OK`
```json
{"valid": true}
```
- `400 Bad Request` (token ausente)
```json
{"valid": false, "msg": "Token e obrigatorio."}
```
- `400 Bad Request` (token inexistente/expirado/ja utilizado)
```json
{"valid": false, "msg": "Token invalido ou expirado."}
```
- `405 Method Not Allowed` para metodos diferentes de `GET`.

---

### 9) POST `/auth/password-reset/confirm/`
Objetivo: concluir redefinicao de senha com token recebido por email.

Payload (JSON):
```json
{
  "token": "string",
  "new_password": "string"
}
```

Retornos:
- `200 OK`
```json
{"msg": "Senha redefinida com sucesso."}
```
- `400 Bad Request` (JSON invalido)
```json
{"msg": "Requisicao invalida."}
```
- `400 Bad Request` (token/senha ausentes)
```json
{"msg": "Token e nova senha sao obrigatorios."}
```
- `400 Bad Request` (token invalido/expirado/ja utilizado)
```json
{"msg": "Token invalido ou expirado."}
```
- `400 Bad Request` (senha nao atende validadores Django)
```json
{"msg": ["<mensagem de validacao>", "..."]}
```
- `405 Method Not Allowed` para metodos diferentes de `POST`.

---

### 10) POST `/auth/email/verify/`
Objetivo: confirmar email do usuario via token de verificacao.

Payload (JSON):
```json
{
  "token": "string"
}
```

Retornos:
- `200 OK`
```json
{"msg": "Email verificado com sucesso."}
```
- `400 Bad Request` (JSON invalido)
```json
{"msg": "Requisicao invalida."}
```
- `400 Bad Request` (token ausente)
```json
{"msg": "Token e obrigatorio."}
```
- `400 Bad Request` (token invalido/expirado/ja utilizado)
```json
{"msg": "Token invalido ou expirado."}
```
- `405 Method Not Allowed` para metodos diferentes de `POST`.

---

### 11) POST `/auth/email/resend-verification/`
Objetivo: reenviar email de verificacao para usuario autenticado.

Payload:
- Body: nao utilizado.
- Cookie obrigatorio: `access_token` valido de usuario no grupo `user`.

Retornos:
- `200 OK` (reenviado)
```json
{"msg": "Email de verificacao reenviado."}
```
- `200 OK` (ja verificado)
```json
{"msg": "Email ja verificado."}
```
- `401 Unauthorized` (sem cookie)
```json
{"msg": "Empty authorization."}
```
- `401 Unauthorized` (token invalido)
```json
{"msg": "<detalhe do simplejwt>"}
```
- `403 Forbidden` (token sem `user_id`, usuario inativo, ou sem permissao de grupo)
```json
{"msg": "User not found."}
```
ou
```json
{"msg": "User not active."}
```
ou
```json
{"msg": "User does not have permission to access this module."}
```
- `429 Too Many Requests` (rate limit por usuario)
```json
{"msg": "Muitas tentativas. Tente novamente mais tarde."}
```
- `405 Method Not Allowed` para metodos diferentes de `POST`.

---

### 12) GET `/auth/social/providers/`
Objetivo: listar provedores OAuth habilitados por configuracao.

Retornos:
- `200 OK`
```json
{
  "providers": [
    {"provider": "google", "name": "Google", "scopes": ["openid", "email", "profile"]}
  ]
}
```

---

### 13) GET `/auth/social/<provider>/authorize/`
Objetivo: iniciar fluxo OAuth e retornar a URL de autorizacao no provedor.

Query params:
- `mode` (opcional): `login` (padrao) ou `link`.
- `frontend_redirect_uri` (opcional): URL final no frontend para receber resultado do callback.

Retornos:
- `200 OK`
```json
{
  "provider": "google",
  "mode": "login",
  "authorize_url": "https://accounts.google.com/..."
}
```
- `401 Unauthorized` quando `mode=link` sem usuario autenticado.
- `404 Not Found` quando provedor nao suportado ou nao configurado.

---

### 14) GET `/auth/social/<provider>/callback/`
Objetivo: concluir OAuth (troca `code`, identifica usuario, cria/vincula conta social e faz login quando aplicavel).

Query params esperados:
- `code`
- `state`

Comportamento:
- Usuario nao autenticado:
1. se ja houver vinculo `provider + provider_user_id`, autentica nessa conta;
2. senao, se email social existir no sistema, vincula e autentica;
3. senao, cria novo usuario, vincula e autentica.
- Usuario autenticado em `mode=link`: vincula a conta social ao usuario atual, mesmo com email diferente.

Retornos:
- `200 OK` JSON (sem `frontend_redirect_uri`) ou `302` redirecionando para frontend.
- `409 Conflict` em conflito de vinculo (conta social ja vinculada a outro usuario).
- `400 Bad Request` para estado OAuth invalido/expirado, perfil sem ID ou falha de troca de token.

---

### 15) GET `/auth/social/accounts/`
Objetivo: listar contas sociais vinculadas ao usuario autenticado.

Retornos:
- `200 OK`
```json
{
  "accounts": [
    {
      "provider": "google",
      "email": "user@example.com",
      "is_email_verified": true,
      "full_name": "User Name",
      "avatar_url": "https://...",
      "linked_at": "2026-03-04T00:00:00+00:00",
      "last_login_at": "2026-03-04T00:30:00+00:00"
    }
  ]
}
```

---

### 16) POST `/auth/social/accounts/<provider>/unlink/`
Objetivo: desvincular conta social do usuario autenticado.

Regras:
- nao permite remover a unica forma de acesso se o usuario nao tiver senha utilizavel.

Retornos:
- `200 OK`
```json
{"msg": "Conta social desvinculada."}
```
- `400 Bad Request` quando a conta social e a unica forma de login.
- `404 Not Found` quando nao existir vinculo para o provedor.

## Fluxos

### Fluxo de login
1. Cliente envia `POST /auth/token/` com `username` e `password`.
2. Backend valida credenciais e responde `200`, gravando cookies `access_token`, `refresh_token` e `lifetimetoken`.
3. Cliente usa `access_token` automaticamente via cookie nas chamadas autenticadas.
4. Opcionalmente, cliente valida sessao com `POST /auth/token/verify/`.

### Fluxo de renovacao de sessao
1. Quando `access_token` expira, cliente chama `POST /auth/token/refresh/`.
2. Backend valida `refresh_token` (cookie) e retorna novo `access_token` em cookie.
3. Se refresh estiver invalido/expirado, cliente deve forcar novo login.

### Fluxo de signout
1. Cliente chama `GET /auth/signout`.
2. Backend remove cookies `access_token`, `refresh_token` e `lifetimetoken`.
3. Cliente fica desautenticado.

### Fluxo de cadastro + verificacao de email
1. Cliente chama `POST /auth/signup`.
2. Backend cria usuario, cria registro `EmailVerification` e gera token de verificacao.
3. Email com link/token e enviado assincronamente.
4. Cliente confirma com `POST /auth/email/verify/` (`token`).
5. Opcional: usuario autenticado pode reenviar com `POST /auth/email/resend-verification/`.

### Fluxo de alterar senha (redefinicao por token)
1. Cliente chama `POST /auth/password-reset/request/` com email.
2. Backend retorna mensagem generica (anti-enumeracao).
3. Usuario recebe token por email (quando aplicavel).
4. Frontend valida token com `GET /auth/password-reset/validate/?token=...`.
5. Frontend envia nova senha via `POST /auth/password-reset/confirm/`.
6. Backend altera senha e invalida token (uso unico).

## Observacoes importantes

- Nao existe endpoint de "alterar senha autenticado" (senha atual -> nova senha) neste app; o fluxo implementado e de redefinicao por token de email.
- Algumas mensagens de erro de token (`<detalhe do simplejwt>`) variam conforme o tipo de falha (expirado, formato invalido, etc.).
- Em `signup` e `token`, JSON malformado nao e tratado explicitamente na view.
- Para habilitar login social e preciso configurar no ambiente:
`SOCIAL_GOOGLE_CLIENT_ID`, `SOCIAL_GOOGLE_CLIENT_SECRET`,
`SOCIAL_DISCORD_CLIENT_ID`, `SOCIAL_DISCORD_CLIENT_SECRET`,
`SOCIAL_GITHUB_CLIENT_ID`, `SOCIAL_GITHUB_CLIENT_SECRET`,
`SOCIAL_FACEBOOK_CLIENT_ID`, `SOCIAL_FACEBOOK_CLIENT_SECRET`,
`SOCIAL_MICROSOFT_CLIENT_ID`, `SOCIAL_MICROSOFT_CLIENT_SECRET`.
