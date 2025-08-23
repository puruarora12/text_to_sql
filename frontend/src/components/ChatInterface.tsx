import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Database, AlertCircle, CheckCircle } from 'lucide-react';
import { conversationService } from '../services/api';
import type { ChatMessage, CreateSessionResponse, AssistantPayload } from '../types/api';

interface ChatInterfaceProps {
  currentSession: CreateSessionResponse | null;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ currentSession }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || !currentSession) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: inputMessage,
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await conversationService.sendMessage({
        session_id: currentSession.session_id,
        messages: [userMessage], // Only send the new message, not the entire history
      });

      // Parse the response to handle complex payload structure
      let assistantContent = 'No response received';
      
      // The conversation endpoint returns the payload directly, not wrapped in a 'response' field
      const payload = response.data;
      
      if (payload) {
        try {
          // If payload is a string, try to parse it as JSON
          const parsedPayload: AssistantPayload = typeof payload === 'string' ? JSON.parse(payload) : payload;
          
          if (parsedPayload.type === 'human_verification') {
            // Check if this is a clarification request or execution confirmation
            if (parsedPayload.requires_clarification && (!parsedPayload.sql || parsedPayload.sql === '')) {
              // This is a clarification request - use the message from the backend
              assistantContent = parsedPayload.message || 'Please provide more specific details about your request.';
            } else {
              // This is an execution confirmation request
              assistantContent = `I've generated a SQL query for you. Would you like me to execute it?\n\n**SQL Query:**\n\`\`\`sql\n${parsedPayload.sql}\n\`\`\`\n\n**Reasoning:** ${parsedPayload.feedback}\n\nPlease respond with "yes" to execute or "no" to cancel.`;
            }
                     } else {
             let content = '';
             
             // Always show SQL query for successful executions
             if (parsedPayload.sql) {
               content += `**SQL Query:**\n\`\`\`sql\n${parsedPayload.sql}\n\`\`\`\n\n`;
             }
             
             // Show decision/status for non-successful cases
             if (parsedPayload.decision && parsedPayload.decision !== 'accept') {
               content += `**Status:** ${parsedPayload.decision}\n\n`;
             }
             
             // Show feedback for non-successful cases
             if (parsedPayload.feedback && parsedPayload.decision !== 'accept') {
               content += `**Feedback:** ${parsedPayload.feedback}\n\n`;
             }
             
             // Show results for successful executions
             if (parsedPayload.rows && parsedPayload.rows.length > 0) {
               content += `**Results (${parsedPayload.row_count} rows):**\n`;
               content += '```\n';
               content += JSON.stringify(parsedPayload.rows, null, 2);
               content += '\n```';
             } else if (parsedPayload.decision === 'accept') {
               // For successful queries with no results
               content += `**Results:** No data found (0 rows)\n`;
             }
             
             assistantContent = content || 'Query processed successfully.';
           }
        } catch (e) {
          // If parsing fails, treat as plain text
          assistantContent = typeof payload === 'string' ? payload : JSON.stringify(payload);
        }
      }

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: assistantContent,
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!currentSession) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Bot size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-600 mb-2">
            No Active Session
          </h3>
          <p className="text-gray-500">
            Please create a session to start chatting with the AI agent.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-white rounded-lg shadow-md">
      {/* Chat Header */}
      <div className="border-b border-gray-200 p-4">
        <h2 className="text-lg font-semibold text-gray-800">
          Chat Session: {currentSession.session_name}
        </h2>
        <p className="text-sm text-gray-500">
          Session ID: {currentSession.session_id}
        </p>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-8">
            <Bot size={32} className="mx-auto mb-2" />
            <p>Start a conversation by sending a message below.</p>
          </div>
        ) : (
          messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                  message.role === 'user'
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                <div className="flex items-start gap-2">
                  {message.role === 'assistant' && (
                    <Bot size={16} className="mt-1 flex-shrink-0" />
                  )}
                                     <div className="flex-1">
                     <div className="text-sm whitespace-pre-wrap">
                       {message.content.split('\n').map((line, lineIndex) => {
                         if (line.startsWith('**') && line.endsWith('**')) {
                           return <div key={lineIndex} className="font-semibold text-gray-800">{line.slice(2, -2)}</div>;
                         } else if (line.startsWith('```sql')) {
                           return <div key={lineIndex} className="bg-gray-100 p-2 rounded font-mono text-xs my-2">{line.slice(6)}</div>;
                         } else if (line.startsWith('```')) {
                           return <div key={lineIndex} className="bg-gray-100 p-2 rounded font-mono text-xs my-2">{line.slice(3)}</div>;
                         } else if (line.trim() === '') {
                           return <div key={lineIndex} className="h-2"></div>;
                         } else {
                           return <div key={lineIndex}>{line}</div>;
                         }
                       })}
                     </div>
                   </div>
                  {message.role === 'user' && (
                    <User size={16} className="mt-1 flex-shrink-0" />
                  )}
                </div>
              </div>
            </div>
          ))
        )}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-800 px-4 py-2 rounded-lg">
              <div className="flex items-center gap-2">
                <Bot size={16} />
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 p-4">
        <form onSubmit={handleSendMessage} className="flex gap-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 input-field"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !inputMessage.trim()}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
};
