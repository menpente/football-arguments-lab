#!/usr/bin/env bash
#
# Run a local Opik stack with docker compose, for tracing pipeline runs.
#
#   scripts/opik-local.sh up       # download + start the stack, wait for health
#   scripts/opik-local.sh down     # stop the stack (keeps data volumes)
#   scripts/opik-local.sh nuke     # stop + delete data volumes
#   scripts/opik-local.sh status   # docker compose ps
#   scripts/opik-local.sh logs [service]
#
# The Opik docker-compose stack is Opik's own, pinned to $OPIK_STACK_VERSION
# and downloaded into .opik/ (gitignored) — this repo does not vendor it.
set -euo pipefail

OPIK_STACK_VERSION="${OPIK_STACK_VERSION:-2.2.52}"
PROJECT="opik-fal"
OPIK_LOCAL_API="http://localhost:5173/api"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK_DIR="$ROOT/.opik/$OPIK_STACK_VERSION"
COMPOSE_DIR="$STACK_DIR/deployment/docker-compose"

need() { command -v "$1" >/dev/null 2>&1 || { echo "error: '$1' not found on PATH" >&2; exit 1; }; }
need docker
need curl
docker compose version >/dev/null 2>&1 || { echo "error: 'docker compose' plugin not available" >&2; exit 1; }

fetch_stack() {
  [ -f "$COMPOSE_DIR/docker-compose.yaml" ] && return
  echo ">> downloading Opik $OPIK_STACK_VERSION compose stack into .opik/"
  mkdir -p "$STACK_DIR"
  curl -fsSL "https://github.com/comet-ml/opik/archive/refs/tags/${OPIK_STACK_VERSION}.tar.gz" \
    | tar -xz -C "$STACK_DIR" --strip-components=1 "opik-${OPIK_STACK_VERSION}/deployment/docker-compose"
}

dc() {
  OPIK_VERSION="$OPIK_STACK_VERSION" docker compose \
    --project-name "$PROJECT" \
    --project-directory "$COMPOSE_DIR" \
    -f "$COMPOSE_DIR/docker-compose.yaml" \
    --profile opik "$@"
}

cmd="${1:-up}"
case "$cmd" in
  up)
    fetch_stack
    echo ">> starting Opik (docker compose --profile opik up -d)"
    dc up -d
    echo ">> waiting for the Opik UI to answer on :5173 ..."
    for _ in $(seq 1 90); do
      if curl -fsS "http://localhost:5173/health" >/dev/null 2>&1; then
        cat <<EOF

Opik is up.
  UI    http://localhost:5173
  API   $OPIK_LOCAL_API

Trace a pipeline run against it:
  export OPIK_TRACING=1
  export OPIK_URL_OVERRIDE=$OPIK_LOCAL_API
  python cli.py run --auto

Stop it later with:  scripts/opik-local.sh down
EOF
        exit 0
      fi
      sleep 2
    done
    echo "error: Opik did not become healthy in time; check 'scripts/opik-local.sh logs'" >&2
    exit 1
    ;;
  down)   fetch_stack; dc down ;;
  nuke)   fetch_stack; dc down -v ;;
  status) fetch_stack; dc ps ;;
  logs)   fetch_stack; shift || true; dc logs -f "$@" ;;
  *)
    echo "usage: $0 [up|down|nuke|status|logs [service]]" >&2
    exit 1
    ;;
esac
