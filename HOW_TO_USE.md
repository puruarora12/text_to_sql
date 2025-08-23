# TextLayer AI Chat System - How to Run



## Prerequisites

- **Python 3.9+** and **Node.js 16+**
- **OpenAI API Key** (required)

## Quick Setup

### 1. Clone and Setup
```bash
git clone <repository-url>
cd textlayer-interview-0.1.3

# Setup backend
make init
source .venv/bin/activate

# Setup frontend
cd frontend
npm install
cd ..
```

### 2. Configure API Key
Create `.env` file in root directory:
```env
FLASK_CONFIG=DEV
OPENAI_API_KEY=sk-your-openai-api-key-here
CHAT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

Create `frontend/.env.local`:
```env
VITE_API_BASE_URL=http://localhost:5000
```

## Run the Application

### Start Backend
```bash
# From root directory
make run
```

### Start Frontend
```bash
# In a new terminal, from root directory
cd frontend
npm run dev
```

### Access the App
- **Frontend**: http://localhost:3000
- **Backend**: http://localhost:5000

## How to Use

1. **Create Session**: Click "Create New Session" and enter a name
2. **Start Chat**: Type natural language queries like:
   - "Show me all customers from New York"
   - "What are the top 10 products by sales?"
   - "Create a table for user preferences"
3. **View Results**: The system will show SQL queries and results

## Troubleshooting

**Backend won't start:**
```bash
# Missing dependencies
source .venv/bin/activate
pip install -r requirements.txt

# Missing API key
# Add OPENAI_API_KEY to .env file
```

**Frontend won't start:**
```bash
# Missing dependencies
cd frontend
npm install
```

**API connection failed:**
- Check that backend is running on port 5000
- Verify VITE_API_BASE_URL in frontend/.env.local

---

That's it! The app should now be running and ready to use.
