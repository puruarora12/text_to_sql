# Text-to-SQL AI Chat System - How to Run

This document provides step-by-step instructions for setting up and running the Text-to-SQL AI Chat application.

## Prerequisites

- Python 3.8 or higher
- Node.js 16 or higher
- Git

## Quick Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd text-to-sql
```

### 2. Backend Setup

1. **Create Virtual Environment**
   ```bash
   python -m venv venv
   ```

2. **Activate Virtual Environment**
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` file with your API keys and configuration.

5. **Run Backend**
   ```bash
   python main.py
   ```

### 3. Frontend Setup

1. **Navigate to Frontend Directory**
   ```bash
   cd frontend
   ```

2. **Install Dependencies**
   ```bash
   npm install
   ```

3. **Start Development Server**
   ```bash
   npm run dev
   ```

## Accessing the Application

- **Backend API**: http://localhost:5000
- **Frontend**: http://localhost:5173 (or port shown in terminal)

## Using the Chat Interface

1. **Create a New Session**: Click "New Session" to start a fresh conversation
2. **Send Messages**: Type your natural language queries in the chat input
3. **View Responses**: The AI will process your request and provide SQL queries or answers
4. **Session History**: Your conversation history is automatically saved

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   - Backend: Change port in `config.py` or kill existing process
   - Frontend: Use `npm run dev -- --port <different-port>`

2. **API Key Errors**
   - Ensure your `.env` file contains valid API keys
   - Check that the backend is running before using the frontend

3. **Dependency Issues**
   - Delete `venv` folder and recreate virtual environment
   - Run `pip install -r requirements.txt` again

### Getting Help

If you encounter issues:
1. Check the console logs for error messages
2. Verify all environment variables are set correctly
3. Ensure both backend and frontend are running

## Development

For development and customization:
- Backend code is in the `app/` directory
- Frontend code is in the `frontend/src/` directory
- API documentation is available at `/v1/` endpoint when backend is running
