import axios from 'axios';
import type { 
  CreateSessionRequest, 
  CreateSessionResponse, 
  ConversationRequest, 
  ConversationResponse,
  ApiResponse 
} from '../types/api';

// Get base URL from environment or use default
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';
const API_VERSION = 'v1';

const api = axios.create({
  baseURL: `${BASE_URL}/${API_VERSION}`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`Making ${config.method?.toUpperCase()} request to ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const sessionService = {
  async createSession(data: CreateSessionRequest): Promise<ApiResponse<CreateSessionResponse>> {
    const response = await api.post('/threads/sessions', data);
    // Backend returns { status, payload, correlation_id }
    return {
      data: response.data.payload,
      message: 'Session created successfully',
      status: response.data.status
    };
  },

  async getSessions(): Promise<ApiResponse<CreateSessionResponse[]>> {
    const response = await api.get('/threads/sessions');
    return {
      data: response.data.payload,
      message: 'Sessions retrieved successfully',
      status: response.data.status
    };
  },
};

export const conversationService = {
  async sendMessage(data: ConversationRequest): Promise<ApiResponse<ConversationResponse>> {
    const response = await api.post('/threads/conversation', data);
    // Backend returns { status, payload, correlation_id }
    return {
      data: response.data.payload,
      message: 'Message sent successfully',
      status: response.data.status
    };
  },

  async chat(messages: { messages: { role: string; content: string }[] }): Promise<ApiResponse<any>> {
    const response = await api.post('/threads/chat', messages);
    return {
      data: response.data.payload,
      message: 'Chat processed successfully',
      status: response.data.status
    };
  },
};

export default api;
