#!/bin/bash

# TextLayer Frontend Startup Script
echo "🚀 Starting TextLayer Frontend..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 16+ from https://nodejs.org/"
    exit 1
else
    NODE_VERSION=$(node --version)
    echo "✅ Node.js found: $NODE_VERSION"
fi

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo "❌ npm not found. Please install npm."
    exit 1
else
    NPM_VERSION=$(npm --version)
    echo "✅ npm found: $NPM_VERSION"
fi

# Check if .env file exists, if not create from example
if [ ! -f ".env" ]; then
    if [ -f "env.example" ]; then
        echo "📝 Creating .env file from env.example..."
        cp env.example .env
        echo "✅ .env file created. You can edit it to change the API URL."
    else
        echo "⚠️  No env.example found. Creating basic .env file..."
        echo "VITE_API_BASE_URL=http://localhost:5000" > .env
    fi
fi

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies."
        exit 1
    fi
    echo "✅ Dependencies installed successfully."
fi

# Start the development server
echo "🌐 Starting development server..."
echo "📱 Frontend will be available at: http://localhost:3000"
echo "🔗 Make sure your backend is running on: http://localhost:5000"
echo ""

npm run dev
