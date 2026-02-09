#!/usr/bin/env bash

ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env.local"

# Function to check if the script is sourced
_is_sourced() { [[ "${BASH_SOURCE[0]}" != "${0}" ]]; }

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE"
  _is_sourced && return 1 || exit 1
fi

# Export all variables from the env file
set -a

. "$ENV_FILE"
set +a

echo "Loaded env from .env.local"
