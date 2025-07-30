#!/bin/bash
set -euo pipefail

# Directories relative to sbc-pay/pay-api
TARGET_DIRS=(
  "../pay-queue"
  "../pay-admin"
  "../jobs/payment-jobs"
)

BRANCH=$(git rev-parse --abbrev-ref HEAD)
REPO=$(git config --get remote.origin.url)

update_pyproject_and_poetry() {
  local dir=$1
  local file="$dir/pyproject.toml"
  if [ ! -f "$file" ]; then
    echo "Skipping $dir: pyproject.toml not found."
    return
  fi

  echo "Updating $file..."
  sed -i -E  "s|pay-api\s*=\s*\{[^}]*subdirectory\s*=\s*\"pay-api\"[^}]*\}|pay-api = { git = \"$REPO\", branch = \"$BRANCH\", subdirectory = \"pay-api\" }|" "$file"

  echo "Running poetry update pay-api in $dir..."
  cd "$dir"
  poetry update pay-api
  cd - > /dev/null
}

for dir in "${TARGET_DIRS[@]}"; do
  update_pyproject_and_poetry "$dir"
done

echo "All done."