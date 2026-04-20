#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Starting app-trs with Docker Compose..."
docker compose up --build
