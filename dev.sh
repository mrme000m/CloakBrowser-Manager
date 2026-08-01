#!/usr/bin/env bash
# CloakBrowser Manager — dev helper.
#
# Two workflows:
#   1) sync   — build the frontend locally and `docker cp` the built dist (and
#               optionally the backend) into the *running* container for a fast
#               test loop. No image rebuild.
#   2) bake  — rebuild the Docker image from the Dockerfile, tag it, and
#               recreate the container (via the compose project that owns it)
#               so the changes are baked into a real image.
#
# The compose project that owns the container is detected from the container's
# labels, so this works regardless of which compose file started it (the lab
# compose at ../cloak-ob2-lab, the repo's own compose, etc.).
#
# Usage:
#   ./dev.sh                 # sync frontend (default; fast, no restart)
#   ./dev.sh sync             #   "    frontend
#   ./dev.sh sync-frontend    #   "    frontend
#   ./dev.sh sync-backend     # cp backend/ in + restart container (kills running browsers)
#   ./dev.sh sync-all         # sync frontend + backend
#   ./dev.sh bake             # rebuild image + recreate container
#   ./dev.sh logs             # docker logs -f <container>
#   ./dev.sh restart          # docker restart <container>
#   ./dev.sh status           # container status + URL + image sha
#   ./dev.sh help
#
# Env overrides:
#   CLOAK_CONTAINER   container name (default: cloak-manager)
#   IMAGE_REPO        image repo    (default: misterme/cloakbrowser-manager)
#   IMAGE_TAG         tag for bake  (default: dev)
#   NO_RECREATE=1     bake builds the image but does not recreate the container
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"

CONTAINER="${CLOAK_CONTAINER:-cloak-manager}"
IMAGE_REPO="${IMAGE_REPO:-misterme/cloakbrowser-manager}"
IMAGE_TAG="${IMAGE_TAG:-dev}"

# ── output helpers ────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  C_BLUE=$'\033[1;34m'; C_GREEN=$'\033[1;32m'; C_YEL=$'\033[1;33m'
  C_RED=$'\033[1;31m'; C_DIM=$'\033[2m'; C_RST=$'\033[0m'
else
  C_BLUE=""; C_GREEN=""; C_YEL=""; C_RED=""; C_DIM=""; C_RST=""
fi
info()  { printf '%s\n' "${C_BLUE}›${C_RST} $*"; }
ok()    { printf '%s\n' "${C_GREEN}✓${C_RST} $*"; }
warn()  { printf '%s\n' "${C_YEL}!${C_RST} $*"; }
err()   { printf '%s\n' "${C_RED}✗${C_RST} $*" >&2; }
step()  { printf '\n%s\n' "${C_BLUE}== $* ==${C_RST}"; }
die()   { err "$*"; exit 1; }

# ── preflight ──────────────────────────────────────────────────────────────
require() { command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"; }
require docker
container_running() {
  [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null || echo false)" == "true" ]]
}
ensure_container() {
  container_running || die "container '$CONTAINER' is not running. Start it first (e.g. from the lab dir: docker compose up -d)."
}

# ── build the frontend locally ──────────────────────────────────────────────
build_frontend() {
  require npm
  [[ -d "$FRONTEND_DIR" ]] || die "frontend dir not found: $FRONTEND_DIR"
  step "Building frontend (npm run build)"
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    info "node_modules missing — installing (npm install)…"
    (cd "$FRONTEND_DIR" && npm install)
  fi
  (cd "$FRONTEND_DIR" && npm run build)
  [[ -f "$FRONTEND_DIR/dist/index.html" ]] || die "build did not produce dist/index.html"
  ok "frontend built → frontend/dist"
}

# ── sync: docker cp into the running container ─────────────────────────────
sync_frontend() {
  ensure_container
  build_frontend
  step "Copying frontend/dist into $CONTAINER:/app/frontend/dist"
  docker cp "$FRONTEND_DIR/dist/." "$CONTAINER:/app/frontend/dist/"
  ok "frontend synced. Hard-refresh the browser (Ctrl+Shift+R) to load new assets."
  warn "no restart needed — static files are served on each request."
}

sync_backend() {
  ensure_container
  [[ -d "$BACKEND_DIR" ]] || die "backend dir not found: $BACKEND_DIR"
  step "Copying backend/ into $CONTAINER:/app/backend"
  docker cp "$BACKEND_DIR/." "$CONTAINER:/app/backend/"
  ok "backend files copied."
  # uvicorn runs as PID 1 without --reload, so a container restart is required
  # to re-import Python. NOTE: the entrypoint kills stale chrome, so any
  # running browser profiles will be stopped by the restart.
  step "Restarting container to reload backend"
  docker restart "$CONTAINER" >/dev/null
  ok "container restarted. Running browser profiles were stopped — relaunch them."
}

sync_all() {
  ensure_container
  build_frontend
  step "Copying frontend/dist + backend/ into $CONTAINER"
  docker cp "$FRONTEND_DIR/dist/." "$CONTAINER:/app/frontend/dist/"
  docker cp "$BACKEND_DIR/." "$CONTAINER:/app/backend/"
  step "Restarting container to reload backend"
  docker restart "$CONTAINER" >/dev/null
  ok "frontend + backend synced and container restarted."
}

# ── bake: rebuild image and recreate the container ─────────────────────────
# Detect the compose project that owns the container from its labels so we
# recreate the *same* container (same name/project/network) rather than a new one.
detect_compose() {
  local labels
  labels=$(docker inspect "$CONTAINER" --format '{{range $k,$v := .Config.Labels}}{{$k}}={{$v}}{{"\n"}}{{end}}' 2>/dev/null || true)
  COMPOSE_FILE="$(printf '%s\n' "$labels"   | sed -n 's/^com.docker.compose.project.config_files=//p' | head -1)"
  COMPOSE_PROJECT="$(printf '%s\n' "$labels" | sed -n 's/^com.docker.compose.project=//p'               | head -1)"
  COMPOSE_WORKDIR="$(printf '%s\n' "$labels"| sed -n 's/^com.docker.compose.project.working_dir=//p'   | head -1)"
  COMPOSE_SERVICE="$(printf '%s\n' "$labels"| sed -n 's/^com.docker.compose.service=//p'                | head -1)"
}

bake() {
  [[ -f "$SCRIPT_DIR/Dockerfile" ]] || die "Dockerfile not found in $SCRIPT_DIR"
  step "Building image $IMAGE_REPO:$IMAGE_TAG"
  DOCKER_BUILDKIT=1 docker build \
    -t "$IMAGE_REPO:$IMAGE_TAG" \
    "$SCRIPT_DIR"
  ok "image built: $IMAGE_REPO:$IMAGE_TAG"

  if [[ "${NO_RECREATE:-0}" == "1" ]]; then
    warn "NO_RECREATE=1 — skipping container recreation."
    info "recreate later with: ./dev.sh bake   (or)   CLOAK_IMAGE_TAG=$IMAGE_TAG docker compose up -d --no-deps <service>"
    return
  fi

  detect_compose
  if [[ -z "$COMPOSE_FILE" || -z "$COMPOSE_PROJECT" || -z "$COMPOSE_SERVICE" ]]; then
    err "could not detect a compose project for '$CONTAINER'."
    info "image is built. Recreate the container manually with:"
    info "    docker stop $CONTAINER && docker rm $CONTAINER"
    info "    docker run -d --name $CONTAINER -p 127.0.0.1:8080:8080 -v ~/.cloakbrowser-manager:/data $IMAGE_REPO:$IMAGE_TAG"
    die "manual recreation required."
  fi

  step "Recreating container via detected compose project"
  info "file:    $COMPOSE_FILE"
  info "project: $COMPOSE_PROJECT"
  info "service: $COMPOSE_SERVICE"
  info "image:   $IMAGE_REPO:$IMAGE_TAG (overriding CLOAK_IMAGE_TAG)"
  # Shell env vars take precedence over .env during compose interpolation, so
  # CLOAK_IMAGE_TAG here points the service at the freshly baked image.
  CLOAK_IMAGE_TAG="$IMAGE_TAG" \
    docker compose \
      -f "$COMPOSE_FILE" \
      --project-directory "${COMPOSE_WORKDIR:-$(dirname "$COMPOSE_FILE")}" \
      -p "$COMPOSE_PROJECT" \
      up -d --no-deps --force-recreate "$COMPOSE_SERVICE"
  ok "container recreated from $IMAGE_REPO:$IMAGE_TAG"
  print_status
}

# ── misc ────────────────────────────────────────────────────────────────────
logs()    { ensure_container; docker logs -f "$CONTAINER"; }
restart() { ensure_container; docker restart "$CONTAINER" >/dev/null && ok "restarted $CONTAINER"; }

print_status() {
  ensure_container
  local state image sha port
  state="$(docker inspect -f '{{.State.Status}}' "$CONTAINER")"
  image="$(docker inspect -f '{{.Config.Image}}' "$CONTAINER")"
  sha="$(docker inspect -f '{{.Image}}' "$CONTAINER" | cut -c1-19)"
  port="$(docker inspect -f '{{range $p,$b := .NetworkSettings.Ports}}{{range $b}}{{.HostIp}}:{{.HostPort}}{{end}}{{end}}' "$CONTAINER" | head -1)"
  printf '\n%s\n' "${C_DIM}── status ──${C_RST}"
  printf '  container : %s (%s)\n' "$CONTAINER" "$state"
  printf '  image    : %s\n' "$image"
  printf '  sha      : %s\n' "$sha"
  printf '  port     : %s\n' "${port:-8080}"
  if [[ -n "${port:-}" ]]; then
    if curl -fsS "http://${port%%:*}:${port##*:}/api/auth/status" >/dev/null 2>&1; then
      printf '  health   : %s reachable at http://%s\n' "${C_GREEN}ok${C_RST}" "$port"
    else
      printf '  health   : %s (still starting?)\n' "${C_YEL}not reachable yet${C_RST}"
    fi
  fi
}

help() {
  sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# ── dispatch ────────────────────────────────────────────────────────────────
cmd="${1:-sync}"
case "$cmd" in
  sync|sync-frontend) sync_frontend ;;
  sync-backend)       sync_backend ;;
  sync-all)           sync_all ;;
  bake)               bake ;;
  logs)               logs ;;
  restart)            restart ;;
  status)             print_status ;;
  help|--help|-h)     help ;;
  *) err "unknown command: $cmd"; help; exit 1 ;;
esac
