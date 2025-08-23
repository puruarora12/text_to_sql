import React, { useState } from 'react';
import { Plus, Users, UserCheck } from 'lucide-react';
import { sessionService } from '../services/api';
import type { CreateSessionResponse } from '../types/api';

interface SessionManagerProps {
  onSessionCreated: (session: CreateSessionResponse) => void;
  currentSession: CreateSessionResponse | null;
}

export const SessionManager: React.FC<SessionManagerProps> = ({ 
  onSessionCreated, 
  currentSession 
}) => {
  const [sessionName, setSessionName] = useState('');
  const [userType, setUserType] = useState<'user' | 'admin'>('user');
  const [isCreating, setIsCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sessionName.trim()) return;

    setIsCreating(true);
    try {
      const response = await sessionService.createSession({
        session_name: sessionName,
        user_type: userType,
      });
      
      onSessionCreated(response.data);
      setSessionName('');
      setShowForm(false);
    } catch (error) {
      console.error('Failed to create session:', error);
      alert('Failed to create session. Please try again.');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="glass-card rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-white">Session Management</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus size={16} />
          New Session
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreateSession} className="mb-6 p-4 glass-effect rounded-xl">
          <div className="mb-4">
            <label htmlFor="sessionName" className="block text-sm font-medium text-white mb-2">
              Session Name
            </label>
            <input
              id="sessionName"
              type="text"
              value={sessionName}
              onChange={(e) => setSessionName(e.target.value)}
              placeholder="Enter session name..."
              className="input-field"
              required
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-white mb-2">
              User Type
            </label>
            <div className="flex gap-4">
              <label className="flex items-center text-white">
                <input
                  type="radio"
                  value="user"
                  checked={userType === 'user'}
                  onChange={(e) => setUserType(e.target.value as 'user' | 'admin')}
                  className="mr-2"
                />
                <Users size={16} className="mr-1" />
                User
              </label>
              <label className="flex items-center text-white">
                <input
                  type="radio"
                  value="admin"
                  checked={userType === 'admin'}
                  onChange={(e) => setUserType(e.target.value as 'user' | 'admin')}
                  className="mr-2"
                />
                <UserCheck size={16} className="mr-1" />
                Admin
              </label>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={isCreating || !sessionName.trim()}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isCreating ? 'Creating...' : 'Create Session'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="btn-secondary"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {currentSession && (
        <div className="glass-effect rounded-xl p-4">
          <h3 className="font-medium text-white mb-2">Current Session</h3>
          <div className="text-sm text-white/80">
            <p><strong>Name:</strong> {currentSession.session_name}</p>
            <p><strong>Type:</strong> {currentSession.user_type}</p>
            <p><strong>ID:</strong> {currentSession.session_id}</p>
          </div>
        </div>
      )}
    </div>
  );
};
