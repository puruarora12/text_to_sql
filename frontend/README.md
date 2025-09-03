# Text-to-SQL Frontend

A modern TypeScript React application for managing sessions and chatting with the Text-to-SQL AI agent.

## Features

- **Session Management**: Create and manage multiple chat sessions
- **Real-time Chat**: Interactive chat interface with AI responses
- **Modern UI**: Clean, responsive design built with Tailwind CSS
- **TypeScript**: Full type safety and better development experience
- **Vite**: Fast development and build tooling

## Prerequisites

- Node.js 16 or higher
- npm or yarn package manager
- Text-to-SQL backend running on localhost:5000

## Quick Start

1. **Install Dependencies**
   ```bash
   npm install
   ```

2. **Start Development Server**
   ```bash
   npm run dev
   ```

3. **Build for Production**
   ```bash
   npm run build
   ```

## Project Structure

```
frontend/
├── src/
│   ├── components/     # React components
│   ├── services/       # API service functions
│   ├── types/          # TypeScript type definitions
│   ├── App.tsx         # Main application component
│   └── main.tsx        # Application entry point
├── public/             # Static assets
├── package.json        # Dependencies and scripts
└── tailwind.config.js  # Tailwind CSS configuration
```

## API Integration

The frontend integrates with the Text-to-SQL API endpoints:

- **Sessions**: Create and manage chat sessions
- **Messages**: Send and receive chat messages
- **Real-time Updates**: Live chat functionality

## Development

- **Hot Reload**: Changes automatically refresh in the browser
- **TypeScript**: Full type checking and IntelliSense support
- **ESLint**: Code quality and consistency
- **Tailwind CSS**: Utility-first CSS framework for styling

## Building

The application uses Vite for fast builds:

```bash
# Development build
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

## Customization

- **Styling**: Modify `tailwind.config.js` for theme changes
- **Components**: Add new components in the `components/` directory
- **API**: Update API endpoints in `services/api.ts`
