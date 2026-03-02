#!/bin/bash
set -euo pipefail

# Directories relative to sbc-pay/pay-api
TARGET_DIRS=(
  "../pay-queue"
  "../pay-admin"
  "../jobs/payment-jobs"
  "../jobs/ftp-poller"
)

REPO=$(git config --get remote.origin.url)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "Fetching latest SHA for branch '$BRANCH' from remote..."
REMOTE_SHA=$(git ls-remote "$REPO" "refs/heads/$BRANCH" | cut -f1)

if [ -z "$REMOTE_SHA" ]; then
    echo "Error: Could not find branch '$BRANCH' on remote. Please push your branch first."
    exit 1
fi

echo "Using Remote SHA: $REMOTE_SHA"

update_pyproject_and_poetry() {
  local dir=$1
  local file="$dir/pyproject.toml"
  if [ ! -f "$file" ]; then
    echo "Skipping $dir: pyproject.toml not found."
    return
  fi

  echo "Updating $file to commit $REMOTE_SHA (Branch: $BRANCH)..."
  
  sed -i -E "s|pay-api\s*=\s*\{[^}]*\}.*|pay-api = { git = \"$REPO\", rev = \"$REMOTE_SHA\", subdirectory = \"pay-api\" } # from branch: $BRANCH|" "$file"

  echo "Running poetry update pay-api in $dir..."
  (
    cd "$dir"
    poetry update pay-api
  )
}

for dir in "${TARGET_DIRS[@]}"; do
  update_pyproject_and_poetry "$dir"
done

echo "All done. All services pinned to remote SHA: $REMOTE_SHA from branch: $BRANCH"
