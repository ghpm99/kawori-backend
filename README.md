# kawori-backend

Backend Django para o ecossistema Kawori — gerenciamento financeiro, integrações com Discord, analytics e recursos ligados a Black Desert Online.

## Tecnologias

- **Python 3.13** / **Django 4.2** / **Django REST Framework**
- **PostgreSQL** como banco de dados
- **JWT (HttpOnly cookies)** para autenticação
- **Sentry** para monitoramento de erros
- **Pusher** para eventos em tempo real
- **WhiteNoise** para servir arquivos estáticos
- **uWSGI** em produção

## Requisitos

- Python 3.13+
- PostgreSQL
- Arquivo `.env` na raiz (use `.env.example` como template)

## Instalação

```bash
# Criar e ativar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais (SECRET_KEY é obrigatória)

# Aplicar migrações
make migrate

# Iniciar servidor de desenvolvimento
make run
```

## Comandos (Makefile)

| Comando | Descrição |
|---------|-----------|
| `make run` | Servidor de desenvolvimento |
| `make test` | Executar todos os testes |
| `make makemigrations` | Gerar migrações |
| `make migrate` | Aplicar migrações |
| `make build` | `collectstatic` para deploy |
| `make version` | Exibir versão da aplicação |
| `make run-release-scripts VERSION=x.y.z` | Executar scripts de release |

Todos os comandos usam `--settings=kawori.settings.development` por padrão.

## Estrutura do projeto

```
kawori/              # Configuração do projeto (settings, URLs, middleware)
authentication/      # Login, logout, signup, refresh de token, CSRF
financial/           # Domínio financeiro (contratos, faturas, pagamentos)
  contract/          # Contratos
  invoice/           # Faturas
  payment/           # Pagamentos
  tag/               # Tags/labels para faturas
  budget/            # Orçamentos vinculados a tags
  earnings/          # Receitas
analytics/           # Analytics
audit/               # Auditoria
classification/      # Classificações
discord/             # Integração com Discord
facetexture/         # Imagens de classes (Black Desert Online)
feature_flag/        # Feature flags
user_profile/        # Perfil de usuário
remote/              # Controle remoto
pusher_webhook/      # Webhook do Pusher
lib/                 # Integrações externas (Google Cloud Storage, Pusher)
scripts/             # Scripts de release e one-offs
docs/                # Documentação operacional
```

## Endpoints principais

| Prefixo | Domínio |
|---------|---------|
| `/auth/` | Autenticação (login, logout, signup, tokens) |
| `/financial/` | Contratos, faturas, pagamentos, tags, orçamentos, receitas |
| `/discord/` | Integração Discord |
| `/facetexture/` | Imagens de classes BDO |
| `/classification/` | Classificações |
| `/profile/` | Perfil do usuário |
| `/analytics/` | Analytics |
| `/remote/` | Controle remoto |
| `/pusher/` | Webhook Pusher |

## Testes

```bash
# Todos os testes
make test

# Testes de um app específico
python manage.py test payment --settings=kawori.settings.development

# Um test case específico
python manage.py test payment.tests.views.test_get_all_view.GetAllViewTestCase --settings=kawori.settings.development
```

## Fluxo de desenvolvimento

1. O trabalho acontece na branch `develop`
2. Automação prepara a release para `main`
3. Aprovação do PR de release é o ponto de decisão
4. A release gera tag, release notes e prepara o deploy
5. One-offs obrigatórios ficam registrados e auditáveis

## Regras obrigatórias

- Toda alteração de código deve existir em commit próprio
- Todo commit que possa chegar em `develop` ou `main` deve seguir **Conventional Commits**
- Toda mudança que exigir one-off, backfill ou passo operacional deve ser registrada em `scripts.xml` e `docs/oneoff-registry.md`

## Documentação operacional

- [`docs/engineering-rules.md`](docs/engineering-rules.md) — Regras de engenharia
- [`docs/release-deploy-plan.md`](docs/release-deploy-plan.md) — Plano de release e deploy
- [`docs/oneoff-registry.md`](docs/oneoff-registry.md) — Registro de one-offs
- [`docs/EMAIL_SETUP.md`](docs/EMAIL_SETUP.md) — Configuração de email
