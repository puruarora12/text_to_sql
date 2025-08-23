import React, { useState } from 'react';
import { MessageCircle, Settings } from 'lucide-react';
import { SessionManager } from './components/SessionManager';
import { ChatInterface } from './components/ChatInterface';
import type { CreateSessionResponse } from './types/api';

function App() {
  const [currentSession, setCurrentSession] = useState<CreateSessionResponse | null>(null);

  const handleSessionCreated = (session: CreateSessionResponse) => {
    setCurrentSession(session);
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <MessageCircle className="h-8 w-8 text-primary-600 mr-3" />
              <h1 className="text-xl font-bold text-gray-900">TextLayer AI Chat</h1>
            </div>
            <div className="flex items-center space-x-4">
              <button className="p-2 text-gray-400 hover:text-gray-600">
                <Settings size={20} />
              </button>
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
      <footer className="bg-white border-t border-gray-200 mt-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-sm text-gray-500">
            TextLayer AI Chat Interface - Powered by Advanced Language Models
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
