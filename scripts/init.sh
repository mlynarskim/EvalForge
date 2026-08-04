#!/bin/sh
set -eu

if [ -f .env ]; then
  echo ".env already exists; no changes made."
  exit 0
fi

session_secret=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
encryption_key=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')

sed \
  -e "s|replace-with-a-random-value-at-least-32-characters|${session_secret}|" \
  -e "s|replace-with-a-fernet-key-generated-by-the-init-script|${encryption_key}|" \
  .env.example > .env

echo "Created .env with fresh local secrets."
echo "Run: docker compose up --build"

