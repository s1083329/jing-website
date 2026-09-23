#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -n "$(git status --porcelain --untracked-files=normal -- . ':!.DS_Store')" ]]; then
  echo 'Commit or stash project changes before deploying.' >&2
  exit 1
fi
test -f .env
test -f instance/database.db
export IMAGE_TAG
IMAGE_TAG="$(git rev-parse HEAD)"
docker compose build --pull web
python3 scripts/backup.py
previous="$(docker inspect --format '{{.Config.Image}}' "$(docker compose ps -q web)" 2>/dev/null || true)"
if docker compose up -d --no-build --wait --wait-timeout 120; then
  echo "Deployed jing-website:$IMAGE_TAG"
  echo "Previous image: ${previous:-none}; retain this image for rollback."
else
  echo 'Deployment unhealthy. Inspect docker compose logs --tail=100 web.' >&2
  if [[ "$previous" == jing-website:* ]]; then
    export IMAGE_TAG="${previous#jing-website:}"
    docker compose up -d --no-build --wait --wait-timeout 120
    echo "Restored $previous" >&2
  fi
  exit 1
fi
