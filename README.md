# kawori-backend

Backend Django para gerenciamento facilitado do bot.

## Documentacao principal

As regras de release, deploy, versionamento e oneoffs ficam em `docs/`:

- `docs/engineering-rules.md`
- `docs/release-deploy-plan.md`
- `docs/oneoff-registry.md`

## Regras obrigatorias

- Toda alteracao de codigo deve existir em commit proprio.
- Todo commit que possa chegar em `develop` ou `main` deve seguir Conventional Commits.
- Toda mudanca que exigir oneoff, backfill, recalc ou passo operacional deve ser registrada em `scripts.xml`.
- Toda mudanca operacional relevante deve ser documentada em `docs/`.

## Objetivo do fluxo

O projeto passa a seguir um fluxo em que:

1. o trabalho acontece em `develop`
2. a automacao prepara a release para `main`
3. a aprovacao do PR de release e o ponto de decisao
4. a release gera tag, release notes e prepara o deploy
5. oneoffs obrigatorios ficam registrados e auditaveis
