#!/usr/bin/env bash

set -e

STORAGE_PATH="./local-storage"

echo "WARNING: This will destroy all containers, volumes, and local storage data."
read -rp "Are you sure? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo "Cleaning up dev environment..."
docker compose --profile dev down -v

if [ -d "$STORAGE_PATH" ]; then
    echo "Removing local storage..."
    rm -rf "$STORAGE_PATH"
fi

echo "Restarting services..."
docker compose --profile dev up -d
