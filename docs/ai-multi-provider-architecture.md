# Arquitetura de IA Multi-Provider (Strategy Pattern)

## 1. Resumo do que foi identificado no projeto relevante para esta implementação

- O backend segue layout modular por domínio (apps Django), com integrações externas em utilitários e configurações centralizadas em `kawori/settings/base.py`.
- O padrão atual usa `requests` com timeout explícito e tratamento de erro por camada de utilidade (ex.: social auth), então a implementação de IA seguiu o mesmo estilo.
- Testes seguem `django.test.TestCase/SimpleTestCase` com mocks/fakes, sem chamadas reais para APIs externas.

## 2. Decisões arquiteturais adotadas

- Foi criado um app leve `ai` (sem models/migrations), integrado ao `INSTALLED_APPS`, mantendo o padrão app-per-domain do repositório.
- Separação de responsabilidades:
  - DTOs e contratos padronizados em `ai/dto.py`.
  - Exceções tipadas em `ai/exceptions.py`.
  - Adapters/gateways de provider em `ai/providers/`.
  - Strategy por tipo de tarefa em `ai/strategies.py`.
  - Router de modelo por task em `ai/routing.py`.
  - Orquestrador com retry/fallback/rastreabilidade em `ai/orchestrator.py`.
- Integração de configuração via settings/env em `kawori/settings/base.py` e `.env.example`.

## 3. Plano objetivo de implementação

1. Criar módulo `ai` com contratos e abstrações centrais.
2. Implementar providers OpenAI/Anthropic via adapter.
3. Implementar estratégias por tipo de tarefa (Strategy Pattern).
4. Implementar roteamento por task com primary/fallback, timeout e retries.
5. Criar orquestrador único para execução e rastreabilidade.
6. Integrar configurações no settings/.env.
7. Cobrir fluxos principais e cenários de erro com testes sem APIs reais.

## 4. Implementação completa

- App `ai` criado e registrado em `kawori/settings/base.py`.
- Abstração central de IA:
  - `AITaskRequest`, `AITaskResponse`, `ProviderCompletionRequest`, `ProviderCompletionResponse`, `ExecutionTraceEntry` em `ai/dto.py`.
- Múltiplos providers suportados:
  - OpenAI Chat Completions em `ai/providers/openai.py`.
  - Anthropic Messages em `ai/providers/anthropic.py`.
  - Fábrica/registro de providers em `ai/factory.py`.
- Strategy Pattern por tipo de tarefa:
  - `text_generation`, `summarization`, `classification`, `structured_extraction`, `simple_task`, `complex_task` em `ai/strategies.py`.
- Seleção de modelo por tipo de tarefa:
  - Roteamento por `AI_TASK_ROUTES` com fallback/retry/timeout em `ai/routing.py`.
- Orquestração resiliente:
  - Retry por modelo, fallback entre modelos e rastreabilidade (`provider/model/attempt/error/trace_id`) em `ai/orchestrator.py`.
- API interna de uso para outras apps:
  - `execute_ai_task()` e construção lazy/cacheada do orquestrador em `ai/utils.py`.
- Configuração:
  - `AI_PROVIDERS`, `AI_TASK_ROUTES`, `AI_DEFAULT_TIMEOUT_SECONDS`, `AI_DEFAULT_MAX_RETRIES`, `AI_ENABLE_FALLBACK` em `kawori/settings/base.py`.
  - Variáveis de ambiente adicionadas em `.env.example`.

## 5. Testes automatizados

- Arquivo: `ai/tests.py`.
- Cobertura implementada:
  - sucesso com strategy correta;
  - retry após timeout;
  - fallback para provider secundário;
  - parsing de classificação em JSON;
  - erro de formato em extração estruturada;
  - uso de rota default quando rota específica não existe.
- Execução validada:
  - `.venv/bin/python manage.py test ai --settings=kawori.settings.test_sqlite`
  - Resultado: `Ran 6 tests ... OK`
- Lint validado:
  - `.venv/bin/python -m flake8 ai kawori/settings/base.py`
  - Resultado: sem erros.

## 6. Exemplo de uso

```python
from ai.dto import AITaskRequest, AITaskType
from ai.utils import execute_ai_task

response = execute_ai_task(
    AITaskRequest(
        task_type=AITaskType.SUMMARIZATION.value,
        input_text="Texto longo...",
        metadata={"max_sentences": 4},
        temperature=0.2,
        max_tokens=300,
    )
)

print(response.output)         # resumo
print(response.provider)       # ex: openai
print(response.model)          # ex: gpt-4o-mini
print(response.trace_id)       # rastreabilidade
print(response.execution_trace)
```

## 7. Como adicionar um novo modelo/provedor

1. Criar adapter novo implementando `AIProviderGateway` (ex.: `ai/providers/novo_provider.py`).
2. Registrar o engine no factory em `ai/factory.py`.
3. Adicionar configuração do provider em `AI_PROVIDERS` no `kawori/settings/base.py`.
4. Configurar rotas em `AI_TASK_ROUTES` para usar esse provider/model por task type.
5. Se houver nova classe de tarefa, adicionar nova Strategy em `ai/strategies.py` e registrar no `build_default_task_strategy_registry`.
6. Adicionar testes com `SequenceProvider` em `ai/tests.py`.

## 8. Pontos de evolução futura

- Cache de respostas por hash de prompt/contexto no orquestrador.
- Métricas/observabilidade (latência, taxa de erro, custo estimado) por `trace_id`.
- Circuit breaker por provider no ponto de chamada `provider.generate`.
- Feature flags por task/model/provider.
- Versionamento de prompts por strategy.
- Execução assíncrona com fila/background jobs sem alterar contratos atuais.
- Política de backoff exponencial nos retries (hoje está imediato).

## 9. Resumo final

A solução foi implementada de forma incremental e integrada ao projeto atual, com arquitetura limpa e desacoplada: contratos estáveis, Strategy por tipo de tarefa, adapters por provider, roteamento configurável por task e orquestrador com retry/fallback/trace. Está pronta para múltiplos modelos/provedores, testada sem APIs reais e preparada para evoluções como cache, métricas e circuit breaker sem quebrar o núcleo.
