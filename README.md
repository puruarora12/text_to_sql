# Text-to-SQL AI Chat Application

A personal project demonstrating the integration of AI language models with database systems to enable natural language to SQL query conversion.

## Overview

This application provides an intelligent chat interface that allows users to interact with databases using natural language. It leverages advanced language models to understand user intent and generate appropriate SQL queries, making database interaction more accessible and user-friendly.

## Features

- **Natural Language Processing**: Convert natural language queries to SQL
- **AI-Powered Chat Interface**: Interactive chat with AI agents
- **Database Integration**: Support for multiple database systems
- **Session Management**: Persistent conversation history
- **Modern Web Interface**: React-based frontend with real-time updates
- **RESTful API**: Clean, documented API endpoints
- **Vector Search**: Intelligent schema understanding and query optimization

## Architecture

The application follows a clean, modular architecture:

- **Backend**: Flask-based API with structured error handling
- **Frontend**: React TypeScript application with modern UI components
- **AI Integration**: LiteLLM for language model management
- **Database**: DuckDB for data storage and vector operations
- **Vector Store**: Semantic search capabilities for schema understanding

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- Docker (optional)

### Backend Setup

1. Clone the repository:
```bash
git clone <your-repo-url>
cd text-to-sql
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the backend:
```bash
python main.py
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

### Docker Deployment

Build and run with Docker:

```bash
docker build -t text-to-sql-app .
docker run -p 5000:5000 text-to-sql-app
```

## API Endpoints

- `GET /v1/` - API information
- `POST /v1/threads` - Create new chat thread
- `POST /v1/threads/{thread_id}/messages` - Send message to thread
- `GET /v1/threads/{thread_id}/messages` - Get thread messages
- `POST /v1/scan` - Database schema scanning

## Project Structure

```
text-to-sql/
├── app/                    # Main application code
│   ├── controllers/       # API controllers
│   ├── services/         # Business logic services
│   ├── routes/           # API route definitions
│   └── schemas/          # Data validation schemas
├── frontend/             # React frontend application
├── config.py             # Configuration settings
└── main.py              # Application entry point
```

## Contributing

This is a personal project for learning and demonstration purposes. Feel free to fork and modify for your own use.

## License

Personal project - use at your own discretion. 

