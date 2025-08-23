import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Database, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
import { conversationService, scanService } from '../services/api';
import type { ChatMessage, CreateSessionResponse, AssistantPayload } from '../types/api';

interface ChatInterfaceProps {
  currentSession: CreateSessionResponse | null;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ currentSession }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [waitingForVerification, setWaitingForVerification] = useState(false);
  const [regenerationInProgress, setRegenerationInProgress] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleRegeneration = async (originalQuery: string, regenerationFeedback: string) => {
    if (!currentSession) return;

    setRegenerationInProgress(true);

    try {
      // Send the original query again with regeneration feedback
      const userMessage: ChatMessage = {
        role: 'user',
        content: originalQuery,
      };

      const apiResponse = await conversationService.sendMessage({
        session_id: currentSession.session_id,
        messages: [userMessage],
      });

      // Process the regenerated response
      const payload = apiResponse.data;
      let assistantContent = 'Regeneration completed.';

      if (payload) {
        try {
          const parsedPayload: AssistantPayload = typeof payload === 'string' ? JSON.parse(payload) : payload;
          
          // Handle the regenerated response
          if (parsedPayload.type === 'human_verification') {
            if (parsedPayload.requires_clarification && (!parsedPayload.sql || parsedPayload.sql === '')) {
              assistantContent = parsedPayload.message || 'Please provide more specific details about your request.';
            } else {
              assistantContent = `I've regenerated the SQL query. Would you like me to execute it?\n\n**SQL Query:**\n\`\`\`sql\n${parsedPayload.sql}\n\`\`\`\n\n**Reasoning:** ${parsedPayload.feedback}\n\n**HUMAN_VERIFICATION_BUTTONS**`;
            }
          } else if (parsedPayload.type === 'regeneration_request') {
            // If regeneration also fails, show error
            assistantContent = `Regeneration failed: ${parsedPayload.user_friendly_message}`;
          } else {
            // Handle successful regeneration
            let content = '';
            
            if (parsedPayload.sql) {
              content += `**Regenerated SQL Query:**\n\`\`\`sql\n${parsedPayload.sql}\n\`\`\`\n\n`;
            }
            
            if (parsedPayload.decision && parsedPayload.decision !== 'accept') {
              content += `**Status:** ${parsedPayload.decision}\n\n`;
            }
            
            if (parsedPayload.feedback && parsedPayload.decision !== 'accept') {
              content += `**Feedback:** ${parsedPayload.feedback}\n\n`;
            }
            
            if (parsedPayload.rows && parsedPayload.rows.length > 0) {
              content += `**Results (${parsedPayload.row_count} rows):**\n`;
              content += '```\n';
              content += JSON.stringify(parsedPayload.rows, null, 2);
              content += '\n```';
            } else if (parsedPayload.decision === 'accept') {
              content += `**Results:** No data found (0 rows)\n`;
            }
            
            assistantContent = content || 'Query regenerated and executed successfully.';
          }
        } catch (e) {
          assistantContent = typeof payload === 'string' ? payload : JSON.stringify(payload);
        }
      }

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: assistantContent,
      };

      setMessages(prev => [...prev, assistantMessage]);
      
      // Check if we're waiting for verification
      if (assistantContent.includes('HUMAN_VERIFICATION_BUTTONS')) {
        setWaitingForVerification(true);
      } else {
        setWaitingForVerification(false);
      }
    } catch (error) {
      console.error('Failed to regenerate SQL:', error);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error during regeneration. Please try again.',
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setRegenerationInProgress(false);
    }
  };

  const handleVerificationButton = async (response: 'yes' | 'no') => {
    if (!currentSession) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: response,
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const apiResponse = await conversationService.sendMessage({
        session_id: currentSession.session_id,
        messages: [userMessage], // Only send the new message, not the entire history
      });

      // Parse the response to handle complex payload structure
      let assistantContent = 'No response received';
      
      // The conversation endpoint returns the payload directly, not wrapped in a 'response' field
      const payload = apiResponse.data;
      
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
              // This is an execution confirmation request - we'll handle this specially with buttons
              assistantContent = `I've generated a SQL query for you. Would you like me to execute it?\n\n**SQL Query:**\n\`\`\`sql\n${parsedPayload.sql}\n\`\`\`\n\n**Reasoning:** ${parsedPayload.feedback}\n\n**HUMAN_VERIFICATION_BUTTONS**`; // Special marker for buttons
            }
          } else if (parsedPayload.type === 'regeneration_request') {
            // Handle SQL regeneration requests
            assistantContent = `SQL execution failed due to a structural issue. I'll try to fix it.\n\n**Error:** ${parsedPayload.user_friendly_message}\n\n**Technical Details:** ${parsedPayload.technical_details}\n\nI'm regenerating the query with the following feedback: ${parsedPayload.feedback}\n\n**REGENERATION_IN_PROGRESS**`;
            
            // Automatically trigger regeneration after a short delay
            setTimeout(() => {
              handleRegeneration(parsedPayload.original_query || '', parsedPayload.feedback || '');
            }, 2000); // 2 second delay to show the regeneration message
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
      
      // Check if we're waiting for verification
      if (assistantContent.includes('HUMAN_VERIFICATION_BUTTONS')) {
        setWaitingForVerification(true);
      } else {
        setWaitingForVerification(false);
      }
    } catch (error) {
      console.error('Failed to send verification response:', error);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
      };
      setMessages(prev => [...prev, errorMessage]);
      setWaitingForVerification(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleScanTables = async () => {
    setIsLoading(true);
    
    try {
      const response = await scanService.getTables();
      const tables = response.data;
      
      // Format the tables data for display
      let content = '**Database Tables Scan Results:**\n\n';
      
      if (tables && Object.keys(tables).length > 0) {
        for (const [tableName, tableInfo] of Object.entries(tables)) {
          const info = tableInfo as any;
          content += `**Table:** ${tableName}\n`;
          content += `**Schema:** ${info.schema}\n`;
          content += `**Columns:** ${info.columns.length}\n`;
          content += `**Sample Rows:** ${info.sample_rows.length}\n\n`;
        }
        content += `**Total Tables:** ${Object.keys(tables).length}`;
      } else {
        content += 'No tables found in the database.';
      }
      
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: content,
      };
      
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to scan tables:', error);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error while scanning tables. Please try again.',
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

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
               // This is an execution confirmation request - we'll handle this specially with buttons
               assistantContent = `I've generated a SQL query for you. Would you like me to execute it?\n\n**SQL Query:**\n\`\`\`sql\n${parsedPayload.sql}\n\`\`\`\n\n**Reasoning:** ${parsedPayload.feedback}\n\n**HUMAN_VERIFICATION_BUTTONS**`; // Special marker for buttons
             }
                     } else if (parsedPayload.type === 'regeneration_request') {
                       // Handle SQL regeneration requests
                       assistantContent = `SQL execution failed due to a structural issue. I'll try to fix it.\n\n**Error:** ${parsedPayload.user_friendly_message}\n\n**Technical Details:** ${parsedPayload.technical_details}\n\nI'm regenerating the query with the following feedback: ${parsedPayload.feedback}\n\n**REGENERATION_IN_PROGRESS**`;
                       
                       // Automatically trigger regeneration after a short delay
                       setTimeout(() => {
                         handleRegeneration(parsedPayload.original_query || '', parsedPayload.feedback || '');
                       }, 2000); // 2 second delay to show the regeneration message
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
      
      // Check if we're waiting for verification
      if (assistantContent.includes('HUMAN_VERIFICATION_BUTTONS')) {
        setWaitingForVerification(true);
      } else {
        setWaitingForVerification(false);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
      };
      setMessages(prev => [...prev, errorMessage]);
      setWaitingForVerification(false);
    } finally {
      setIsLoading(false);
    }
  };

  if (!currentSession) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center glass-card p-8 rounded-2xl">
          <Bot size={48} className="mx-auto text-white/80 mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">
            No Active Session
          </h3>
          <p className="text-white/70">
            Please create a session to start chatting with the AI agent.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col glass-effect rounded-2xl">
      {/* Chat Header */}
      <div className="border-b border-white/20 p-6">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-xl font-semibold text-white">
              Chat Session: {currentSession.session_name}
            </h2>
            <p className="text-sm text-white/70">
              Session ID: {currentSession.session_id}
            </p>
          </div>
          <button
            onClick={handleScanTables}
            disabled={isLoading}
            className="btn-secondary flex items-center gap-2"
            title="Scan database tables"
          >
            <RefreshCw size={16} />
            Scan Tables
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-white/60 mt-8">
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
                className={`max-w-xs lg:max-w-md px-4 py-3 rounded-xl chat-bubble ${
                  message.role === 'user'
                    ? 'chat-bubble-user'
                    : 'chat-bubble-assistant'
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
                             return <div key={lineIndex} className="font-semibold text-white">{line.slice(2, -2)}</div>;
                           } else if (line.startsWith('```sql')) {
                             return <div key={lineIndex} className="bg-black/20 backdrop-blur-sm p-3 rounded-lg font-mono text-xs my-2 border border-white/10">{line.slice(6)}</div>;
                           } else if (line.startsWith('```')) {
                             return <div key={lineIndex} className="bg-black/20 backdrop-blur-sm p-3 rounded-lg font-mono text-xs my-2 border border-white/10">{line.slice(3)}</div>;
                           } else if (line.trim() === '') {
                             return <div key={lineIndex} className="h-2"></div>;
                           } else if (line.includes('HUMAN_VERIFICATION_BUTTONS')) {
                             // Replace the marker with buttons
                             return (
                               <div key={lineIndex} className="mt-4 flex gap-3">
                                 <button
                                   onClick={() => handleVerificationButton('yes')}
                                   disabled={isLoading}
                                   className="btn-success"
                                 >
                                   <CheckCircle size={16} />
                                   Yes, Execute
                                 </button>
                                 <button
                                   onClick={() => handleVerificationButton('no')}
                                   disabled={isLoading}
                                   className="btn-danger"
                                 >
                                   <AlertCircle size={16} />
                                   No, Cancel
                                 </button>
                               </div>
                             );
                           } else if (line.includes('REGENERATION_IN_PROGRESS')) {
                             // Replace the marker with regeneration progress indicator
                             return (
                               <div key={lineIndex} className="mt-4 flex items-center gap-2 text-amber-600">
                                 <div className="flex space-x-1">
                                   <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce"></div>
                                   <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                                   <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                                 </div>
                                 <span className="text-sm font-medium">Regenerating SQL query...</span>
                               </div>
                             );
                           } else {
                             return <div key={lineIndex}>{line}</div>;
                           }
                         })}
                         {/* Add buttons at the end if the message contains the marker */}
                         {message.content.includes('HUMAN_VERIFICATION_BUTTONS') && (
                           <div className="mt-4 flex gap-3">
                             <button
                               onClick={() => handleVerificationButton('yes')}
                               disabled={isLoading}
                               className="btn-success"
                             >
                               <CheckCircle size={16} />
                               Yes, Execute
                             </button>
                             <button
                               onClick={() => handleVerificationButton('no')}
                               disabled={isLoading}
                               className="btn-danger"
                             >
                               <AlertCircle size={16} />
                               No, Cancel
                             </button>
                           </div>
                         )}
                         {/* Add regeneration progress indicator if the message contains the marker */}
                         {message.content.includes('REGENERATION_IN_PROGRESS') && (
                           <div className="mt-4 flex items-center gap-2 text-amber-600">
                             <div className="flex space-x-1">
                               <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce"></div>
                               <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                               <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                             </div>
                             <span className="text-sm font-medium">Regenerating SQL query...</span>
                           </div>
                         )}
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
        
        {(isLoading || regenerationInProgress) && (
          <div className="flex justify-start">
            <div className="chat-bubble-assistant chat-bubble px-4 py-3 rounded-xl">
              <div className="flex items-center gap-2">
                <Bot size={16} />
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-white/20 p-6">
        {waitingForVerification && (
          <div className="mb-4 p-4 notification-banner rounded-xl">
            <div className="flex items-center gap-2 text-amber-800">
              <AlertCircle size={16} />
              <span className="text-sm font-medium">Please verify the SQL query execution above</span>
            </div>
          </div>
        )}
        {regenerationInProgress && (
          <div className="mb-4 p-4 notification-banner rounded-xl">
            <div className="flex items-center gap-2 text-amber-800">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
              <span className="text-sm font-medium">Regenerating SQL query...</span>
            </div>
          </div>
        )}
        <form onSubmit={handleSendMessage} className="flex gap-3">
                               <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 input-field"
            disabled={isLoading || waitingForVerification || regenerationInProgress}
          />
          <button
            type="submit"
            disabled={isLoading || !inputMessage.trim() || waitingForVerification || regenerationInProgress}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
};
