#!/usr/bin/env bash
# Deploy the latest code to this server, in one command.
#
#     bash deploy/deploy.sh
#
# Run it on the server (after `ssh` in), from anywhere inside the repository.
# It pulls the latest main, rebuilds and restarts the containers, waits until
# the backend reports healthy, and checks the public address. If anything goes
# wrong it stops, says what, and shows the end of the backend log.
#
# Safe to run any time: with no new code it just makes sure the containers are
# up to date with the code and with .env (so it is also how you apply a changed
# setting). Database migrations run by themselves when the backend starts.
#
# Settings (environment variables, both optional):
#     WAIT_SECONDS   how long to wait for the backend to become healthy (default 180)

set -euo pipefail

# Everything runs inside main(), called on the last line. Bash therefore reads the
# whole script before running any of it, so `git pull` replacing this very file
# part way through (when a change touches deploy.sh) cannot confuse the run.
main() {

  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  COMPOSE="docker compose -f docker-compose.prod.yml"
  WAIT_SECONDS="${WAIT_SECONDS:-180}"

  step() { printf '\n==> %s\n' "$*"; }

  old=$(git rev-parse --short HEAD)

  fail() {
    printf '\nDEPLOY FAILED: %s\n' "$1" >&2
    printf '\nThe end of the backend log:\n' >&2
    $COMPOSE logs --tail 40 backend >&2 || true
    printf '\nTo go back to the version that was running (database migrations are not undone):\n' >&2
    printf '    git reset --hard %s && bash deploy/deploy.sh\n' "$old" >&2
    exit 1
  }

  [ -f .env ] || { echo "There is no .env in $(pwd). See deploy/README.md, step 4." >&2; exit 1; }

  step "Pulling the latest code (now at $old)"
  git pull --ff-only
  new=$(git rev-parse --short HEAD)
  if [ "$old" != "$new" ]; then
    echo "Updated $old -> $new:"
    git log --oneline "$old..$new"
  fi

  step "Building and starting the containers"
  $COMPOSE up -d --build || fail "docker compose could not build or start the containers."

  step "Waiting for the backend to be healthy (up to ${WAIT_SECONDS}s)"
  backend=$($COMPOSE ps -q backend)
  [ -n "$backend" ] || fail "the backend container is not running."
  deadline=$((SECONDS + WAIT_SECONDS))
  while true; do
    status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$backend" 2>/dev/null || echo unknown)
    if [ "$status" = "healthy" ]; then
      echo "The backend is healthy."
      break
    fi
    [ "$SECONDS" -lt "$deadline" ] || fail "the backend is still '$status' after ${WAIT_SECONDS}s."
    sleep 3
  done

  host=$(grep -E '^API_HOST=' .env | head -n1 | cut -d= -f2- | tr -d "\"' " || true)
  if [ -n "$host" ]; then
    step "Checking https://$host/health"
    for attempt in 1 2 3 4 5; do
      if body=$(curl -fsS --max-time 10 "https://$host/health"); then
        echo "$body"
        break
      fi
      [ "$attempt" -lt 5 ] || fail "https://$host/health did not answer (Caddy may still be getting its certificate; try again in a minute)."
      sleep 3
    done
  fi

  step "Containers"
  $COMPOSE ps
  printf '\nDeployed %s.\n' "$new"
}

main "$@"
exit
