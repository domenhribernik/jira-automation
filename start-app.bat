@echo off
setlocal

if not exist nginx\conf.d mkdir nginx\conf.d
if not exist nginx\ssl mkdir nginx\ssl
if not exist logs mkdir logs

if not exist nginx\conf.d\app.conf (
    echo Creating Nginx configuration file...
    copy nginx-config-template.conf nginx\conf.d\app.conf
)

echo Starting in PRODUCTION mode...
    
if not exist .env (
    echo ERROR: .env file not found! Please create one based on .env.example.
    exit /b 1
)

docker-compose up -d --build

echo Application started in production mode.
echo To view logs, run: docker-compose logs -f

endlocal