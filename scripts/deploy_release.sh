#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
SETTINGS_MODULE="${SETTINGS_MODULE:-kawori.settings.production}"
STATE_DIR="${STATE_DIR:-$ROOT_DIR/.deploy}"
STATE_FILE="${STATE_FILE:-$STATE_DIR/current_version}"
TARGET_TAG="${1:-}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON_BIN_FALLBACK:-python}"
fi

mkdir -p "$STATE_DIR"

git fetch origin --tags

if [[ -z "$TARGET_TAG" ]]; then
  TARGET_TAG="$(git tag --list 'v*' --sort=-version:refname | head -n 1)"
fi

if [[ -z "$TARGET_TAG" ]]; then
  echo "No release tag found."
  exit 1
fi

CURRENT_VERSION=""
if [[ -f "$STATE_FILE" ]]; then
  CURRENT_VERSION="$(cat "$STATE_FILE")"
fi

if [[ "$CURRENT_VERSION" == "$TARGET_TAG" ]]; then
  echo "Version $TARGET_TAG is already deployed."
  exit 0
fi

echo "Deploying $TARGET_TAG"
git checkout "$TARGET_TAG"

"$PYTHON_BIN" -m pip install -r requirements.txt
"$PYTHON_BIN" manage.py migrate --settings="$SETTINGS_MODULE"
"$PYTHON_BIN" manage.py collectstatic --noinput --settings="$SETTINGS_MODULE"
"$PYTHON_BIN" manage.py run_release_scripts --target-version "$TARGET_TAG" --settings="$SETTINGS_MODULE"

if [[ -n "${APP_RESTART_COMMAND:-}" ]]; then
  eval "$APP_RESTART_COMMAND"
else
  echo "APP_RESTART_COMMAND not set, skipping service restart."
fi

printf '%s' "$TARGET_TAG" > "$STATE_FILE"
echo "Deployment completed for $TARGET_TAG"
