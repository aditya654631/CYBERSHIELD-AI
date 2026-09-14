import axios from 'axios';
import {
  Complaint,
  ComplaintCreate,
  Prediction,
  Explanation,
  GraphData,
  HotspotCluster,
  ATMLocationItem,
  AlertItem,
  AnalyticsOverview,
  DashboardSummary,
  AuditLogItem,
  ModelPerformanceData,
} from '../types';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  'https://cybershield-ai-production-66121.up.railway.app/api/v1';

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
  getComplaints: async (params?: { fraud_type?: string; risk_level?: string; search?: string; limit?: number; skip?: number; state?: string }) => {
    const res = await apiClient.get<Complaint[]>('/complaints', { params });
    return res.data;
  },
  getComplaintsRegistry: async (params?: {
    fraud_type?: string;
    case_status?: string;
    district?: string;
    prediction_status?: string;
    alert_status?: string;
    search?: string;
    page?: number;
    limit?: number;
    state?: string;
  }): Promise<{ complaints: Complaint[]; total: number; page: number; totalPages: number }> => {
    const res = await apiClient.get<Complaint[]>('/complaints', { params });
    const total = parseInt(res.headers['x-total-count'] || `${res.data.length}`, 10);
    const page = parseInt(res.headers['x-page'] || '1', 10);
    const limit = params?.limit || 25;
    const totalPages = parseInt(res.headers['x-total-pages'] || `${Math.max(1, Math.ceil(total / limit))}`, 10);
    return {
      complaints: res.data,
      total,
      page,
      totalPages,
    };
  },
  getComplaint: async (id: string | number) => {
    const res = await apiClient.get<Complaint>(`/complaints/${id}`);
    return res.data;
  },
  createComplaint: async (data: ComplaintCreate) => {
    const res = await apiClient.post<Complaint>('/complaints', data);
    return res.data;
  },

  // Predictions & Explainability
  runPrediction: async (complaintId: string | number) => {
    const res = await apiClient.post<Prediction>(`/predictions/${complaintId}`);
    return res.data;
  },
  getPrediction: async (complaintId: string | number) => {
    try {
      const res = await apiClient.get<Prediction>(`/predictions/${complaintId}`);
      return res.data;
    } catch (err: any) {
      if (err.response?.status === 404) {
        return null;
      }
      throw err;
    }
  },
  getExplanation: async (predictionId: number) => {
    const res = await apiClient.get<Explanation>(`/predictions/${predictionId}/explanation`);
    return res.data;
  },
  verifyPredictionAudit: async (predictionId: number) => {
    const res = await apiClient.get<any>(`/predictions/${predictionId}/audit-verification`);
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
  createAlertForPrediction: async (predictionId: number) => {
    const res = await apiClient.post<AlertItem>(`/alerts/prediction/${predictionId}`);
    return res.data;
  },
  generateAlertForComplaint: async (complaintId: string | number) => {
    const res = await apiClient.post<AlertItem>(`/alerts/generate/${complaintId}`);
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
  getDashboardSummary: async () => {
    const res = await apiClient.get<DashboardSummary>('/dashboard/summary');
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
