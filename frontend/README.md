# TextLayer Frontend

A modern TypeScript React application for managing sessions and chatting with the TextLayer AI agent.

## Features

- 🚀 Modern React with TypeScript
- 🎨 Beautiful UI with Tailwind CSS
- 💬 Real-time chat interface
- 🔧 Session management
- 📱 Responsive design
- ⚡ Fast development with Vite

## Prerequisites

- Node.js 16+ 
- npm or yarn
- TextLayer backend running on localhost:5000

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure environment:**
   ```bash
   cp env.example .env
   ```
   
   Edit `.env` and set your API base URL:
   ```
   VITE_API_BASE_URL=http://localhost:5000
   ```

3. **Start development server:**
   ```bash
   npm run dev
   ```

4. **Open your browser:**
   Navigate to `http://localhost:3000`

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Project Structure

```
src/
├── components/          # React components
│   ├── ChatInterface.tsx
│   └── SessionManager.tsx
├── services/           # API services
│   └── api.ts
├── types/              # TypeScript type definitions
│   └── api.ts
├── App.tsx            # Main application component
├── main.tsx           # Application entry point
└── index.css          # Global styles
```

## API Integration

The frontend integrates with the TextLayer API endpoints:

- `POST /v1/threads/sessions` - Create new session
- `POST /v1/threads/conversation` - Send chat messages
- `POST /v1/threads/chat` - Direct chat endpoint

## Technologies Used

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling
- **Axios** - HTTP client
- **Lucide React** - Icons

## Development

The application uses Vite for fast development with hot module replacement. The development server includes a proxy configuration to forward API requests to the backend.

## Building for Production

```bash
npm run build
```

This creates an optimized production build in the `dist/` directory.
