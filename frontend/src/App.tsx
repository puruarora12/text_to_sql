import React, { useState } from 'react';
import './App.css';
import { ChatInterface } from './components/ChatInterface';
import { SessionManager } from './components/SessionManager';
import type { CreateSessionResponse } from './types/api';

function App() {
  const [currentSession, setCurrentSession] = useState<CreateSessionResponse | null>(null);

  const handleSessionCreated = (session: CreateSessionResponse) => {
    setCurrentSession(session);
  };

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-bold text-white">Text-to-SQL AI Chat</h1>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-gray-300 text-sm">AI-Powered Database Queries</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Session Management Sidebar */}
          <div className="lg:col-span-1">
            <SessionManager
              onSessionCreated={handleSessionCreated}
              currentSession={currentSession}
            />
          </div>

          {/* Chat Interface */}
          <div className="lg:col-span-2">
            <ChatInterface currentSession={currentSession} />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="text-center text-gray-400 text-sm">
            Text-to-SQL AI Chat Interface - Powered by Advanced Language Models
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
