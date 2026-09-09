import axios from 'axios';
import {
  Complaint,
  Prediction,
  Explanation,
  GraphData,
  HotspotCluster,
  ATMLocationItem,
  AlertItem,
  AnalyticsOverview,
  AuditLogItem,
  ModelPerformanceData,
} from '../types';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor for attaching JWT Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('cybershield_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Interceptor for handling 401 Unauthorized / Token Expiration
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('cybershield_token');
      localStorage.removeItem('cybershield_user');
      window.dispatchEvent(new CustomEvent('auth:expired'));
    }
    return Promise.reject(error);
  }
);

export const api = {
  // Auth
  login: async (email: string, password: string) => {
    const res = await apiClient.post('/auth/login', { email, password });
    return res.data;
  },
  getMe: async () => {
    const res = await apiClient.get('/auth/me');
    return res.data;
  },

  // Complaints
  getComplaints: async (params?: { fraud_type?: string; risk_level?: string; search?: string; limit?: number; skip?: number }) => {
    const res = await apiClient.get<Complaint[]>('/complaints', { params });
    return res.data;
  },
  getComplaint: async (id: string | number) => {
    const res = await apiClient.get<Complaint>(`/complaints/${id}`);
    return res.data;
  },
  createComplaint: async (data: {
    fraud_type: string;
    amount: number;
    victim_location: string;
    state?: string;
    district?: string;
    payment_channel?: string;
    victim_name?: string;
    victim_phone?: string;
  }) => {
    const res = await apiClient.post<Complaint>('/complaints', data);
    return res.data;
  },

  // Predictions & Explainability
  runPrediction: async (complaintId: string | number) => {
    const res = await apiClient.post<Prediction>(`/predictions/${complaintId}`);
    return res.data;
  },
  getPrediction: async (complaintId: string | number) => {
    const res = await apiClient.get<Prediction>(`/predictions/${complaintId}`);
    return res.data;
  },
  getExplanation: async (predictionId: number) => {
    const res = await apiClient.get<Explanation>(`/predictions/${predictionId}/explanation`);
    return res.data;
  },

  // Graphs
  getGraph: async (complaintId: string | number) => {
    const res = await apiClient.get<GraphData>(`/complaints/${complaintId}/graph`);
    return res.data;
  },

  // GIS
  getRiskMap: async (params?: { district?: string; risk_level?: string }) => {
    const res = await apiClient.get<{
      hotspots: HotspotCluster[];
      atms: ATMLocationItem[];
      summary: any;
    }>('/risk-map', { params });
    return res.data;
  },
  getClusters: async () => {
    const res = await apiClient.get<HotspotCluster[]>('/clusters');
    return res.data;
  },

  // Alerts
  getAlerts: async (params?: { status?: string; severity?: string }) => {
    const res = await apiClient.get<AlertItem[]>('/alerts', { params });
    return res.data;
  },
  acknowledgeAlert: async (alertId: number, notes?: string) => {
    const res = await apiClient.post<AlertItem>(`/alerts/${alertId}/acknowledge`, { notes });
    return res.data;
  },
  escalateAlert: async (alertId: number, notes?: string) => {
    const res = await apiClient.post<AlertItem>(`/alerts/${alertId}/escalate`, { notes });
    return res.data;
  },

  // Analytics
  getAnalyticsOverview: async () => {
    const res = await apiClient.get<AnalyticsOverview>('/analytics/overview');
    return res.data;
  },

  // Model Performance
  getModelPerformance: async () => {
    const res = await apiClient.get<ModelPerformanceData>('/model/performance');
    return res.data;
  },

  // Audit
  getAuditLogs: async (params?: { action?: string }) => {
    const res = await apiClient.get<AuditLogItem[]>('/audit', { params });
    return res.data;
  },
};
