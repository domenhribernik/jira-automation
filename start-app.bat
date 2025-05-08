@echo off
setlocal

:: Create necessary directories
if not exist nginx\conf.d mkdir nginx\conf.d
if not exist nginx\ssl mkdir nginx\ssl
if not exist logs mkdir logs

:: Check if Nginx config exists, if not create it
if not exist nginx\conf.d\app.conf (
    echo Creating Nginx configuration file...
    copy nginx-config-template.conf nginx\conf.d\app.conf
)

:: Check if running in development or production mode
if "%1"=="dev" (
    echo Starting in DEVELOPMENT mode...
    copy .env.dev .env
    docker-compose up --build
) else (
    echo Starting in PRODUCTION mode...
    
    :: Check if .env exists
    if not exist .env (
        echo ERROR: .env file not found! Please create one based on .env.example.
        exit /b 1
    )
    
    :: Start containers in detached mode
    docker-compose up -d --build
    
    echo Application started in production mode.
    echo To view logs, run: docker-compose logs -f
)

endlocal