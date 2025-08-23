import React, { useState } from 'react';
import { Settings } from 'lucide-react';
import { SessionManager } from './components/SessionManager';
import { ChatInterface } from './components/ChatInterface';
import type { CreateSessionResponse } from './types/api';
import logo from './logo.png';

function App() {
  const [currentSession, setCurrentSession] = useState<CreateSessionResponse | null>(null);

  const handleSessionCreated = (session: CreateSessionResponse) => {
    setCurrentSession(session);
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="glass-effect border-b border-white/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <img src={logo} alt="TextLayer Logo" className="h-8 w-8 mr-3 logo" />
              <h1 className="text-xl font-bold text-white">TextLayer AI Chat</h1>
            </div>
            <div className="flex items-center space-x-4">
              <button className="p-2 text-white/70 hover:text-white transition-colors">
                <Settings size={20} />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
      <footer className="glass-effect border-t border-white/20 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-sm text-white/70">
            TextLayer AI Chat Interface - Powered by Advanced Language Models
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
