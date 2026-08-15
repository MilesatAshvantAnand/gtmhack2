#!/usr/bin/env bash

set -euo pipefail

repository="bilalahmad20/ai-gtm-hackathon-baseline"
secrets=(
  ZENABM_HACKATHON_TOKEN
  HUBSPOT_HACKATHON_TOKEN
  UNIFYGTM_HACKATHON_API_KEY
  OPENAI_HACKATHON_API_KEY
)

for secret_name in "${secrets[@]}"; do
  read -r -s -p "Enter ${secret_name} (leave blank to skip): " secret_value
  echo

  if [[ -n "$secret_value" ]]; then
    printf '%s' "$secret_value" | gh secret set --app codespaces --repo "$repository" "$secret_name"
    unset secret_value
  fi
done
