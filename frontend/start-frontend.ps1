# TextLayer Frontend Startup Script
Write-Host "Starting TextLayer Frontend..." -ForegroundColor Green

# Check if Node.js is installed
try {
    $nodeVersion = node --version
    Write-Host "Node.js found: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "Node.js not found. Please install Node.js 16+ from https://nodejs.org/" -ForegroundColor Red
    exit 1
}

# Check if npm is available
try {
    $npmVersion = npm --version
    Write-Host "npm found: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "npm not found. Please install npm." -ForegroundColor Red
    exit 1
}

# Check if .env file exists, if not create from example
if (-not (Test-Path ".env")) {
    if (Test-Path "env.example") {
        Write-Host "Creating .env file from env.example..." -ForegroundColor Yellow
        Copy-Item "env.example" ".env"
        Write-Host ".env file created. You can edit it to change the API URL." -ForegroundColor Green
    } else {
        Write-Host "No env.example found. Creating basic .env file..." -ForegroundColor Yellow
        "VITE_API_BASE_URL=http://localhost:5000" | Out-File -FilePath ".env" -Encoding UTF8
    }
}

# Install dependencies if node_modules doesn't exist
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install dependencies." -ForegroundColor Red
        exit 1
    }
    Write-Host "Dependencies installed successfully." -ForegroundColor Green
}

# Start the development server
Write-Host "Starting development server..." -ForegroundColor Yellow
Write-Host "Frontend will be available at: http://localhost:3000" -ForegroundColor Cyan
Write-Host "Make sure your backend is running on: http://localhost:5000" -ForegroundColor Cyan
Write-Host ""

npm run dev
