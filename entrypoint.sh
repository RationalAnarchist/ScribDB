#!/bin/bash
set -e

# Ensure config directory exists
if [ ! -d "/app/config" ]; then
    echo "Creating config directory..."
    mkdir -p /app/config
fi

# Copy alembic.ini if missing
if [ ! -f "/app/config/alembic.ini" ]; then
    echo "Initializing alembic.ini..."
    if [ -f "/app/defaults/config/alembic.ini" ]; then
        cp /app/defaults/config/alembic.ini /app/config/alembic.ini
    else
        echo "Warning: /app/defaults/config/alembic.ini not found."
    fi
fi

# Copy config.json.example if missing
if [ ! -f "/app/config/config.json.example" ]; then
    echo "Initializing config.json.example..."
    if [ -f "/app/defaults/config/config.json.example" ]; then
        cp /app/defaults/config/config.json.example /app/config/config.json.example
    else
        echo "Warning: /app/defaults/config/config.json.example not found."
    fi
fi

# If config.json is missing, create it from example
if [ ! -f "/app/config/config.json" ]; then
    echo "Initializing config.json from example..."
    if [ -f "/app/config/config.json.example" ]; then
        cp /app/config/config.json.example /app/config/config.json
    else
        echo "Warning: Could not create config.json (example missing)."
    fi
fi

exec "$@"
