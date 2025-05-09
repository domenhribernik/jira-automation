#!/bin/bash

# Create necessary directories if they don't exist
mkdir -p nginx/conf.d
mkdir -p nginx/ssl
mkdir -p logs

# Check if the Nginx configuration file exists, if not, create it
if [ ! -f nginx/conf.d/app.conf ]; then
    cp nginx-config-template.conf nginx/conf.d/app.conf
    echo "Created Nginx configuration file."
fi


echo "Starting in PRODUCTION mode..."
# Make sure .env exists (use .env.example as a template if it doesn't)
if [ ! -f .env ]; then
    echo "ERROR: .env file not found! Please create one based on .env.example."
    exit 1
fi
    
# Start containers in detached mode
docker compose up -d --build

echo "Application started in production mode."
echo "To view logs, run: docker-compose logs -f"
