#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

log() { printf '\n[StorServer] %s\n' "$*"; }
fail() { printf '\n[StorServer] ERRO: %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "Docker não encontrado."
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin não encontrado."

random_hex() {
  local bytes="${1:-32}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
  else
    od -An -N "$bytes" -tx1 /dev/urandom | tr -d ' \n'
  fi
}

NEW_ENV=0
if [[ ! -f .env ]]; then
  [[ -f .env.example ]] || fail ".env.example não encontrado."
  log "Criando .env seguro a partir do .env.example..."
  umask 077
  cp .env.example .env

  JWT_SECRET="$(random_hex 48)"
  DB_PASSWORD="$(random_hex 24)"
  AGENT_TOKEN="$(random_hex 32)"
  ADMIN_PASSWORD="$(random_hex 12)"

  sed -i \
    -e "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASSWORD}|" \
    -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://storserver:${DB_PASSWORD}@postgres:5432/storserver|" \
    -e "s|^AGENT_SHARED_TOKEN=.*|AGENT_SHARED_TOKEN=${AGENT_TOKEN}|" \
    -e "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${ADMIN_PASSWORD}|" \
    .env

  NEW_ENV=1
else
  log ".env já existe; mantendo configuração e segredos atuais."
fi

mkdir -p storage data backups

log "Validando Docker Compose..."
docker compose config >/dev/null

log "Construindo e iniciando StorServer..."
docker compose up -d --build

log "Estado dos serviços:"
docker compose ps

ADMIN_EMAIL="$(grep -E '^ADMIN_EMAIL=' .env | head -n1 | cut -d= -f2-)"
ADMIN_PASSWORD="$(grep -E '^ADMIN_PASSWORD=' .env | head -n1 | cut -d= -f2-)"

printf '\n============================================================\n'
printf ' StorServer iniciado\n'
printf '============================================================\n'
printf ' Painel:     http://SEU-IP:3000\n'
printf ' API Docs:   http://SEU-IP:8000/docs\n'
printf ' Admin:      %s\n' "${ADMIN_EMAIL:-admin@hoststorm.cloud}"
printf ' Senha:      %s\n' "${ADMIN_PASSWORD:-consulte o arquivo .env}"
printf '============================================================\n'

if [[ "$NEW_ENV" -eq 1 ]]; then
  printf '\nIMPORTANTE: a senha acima foi gerada automaticamente. Guarde-a.\n'
fi
