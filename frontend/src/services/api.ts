import axios from 'axios';
import {
  Complaint,
  ComplaintCreate,
  Prediction,
  PredictionVersionSummary,
  Explanation,
  GraphData,
  HotspotCluster,
  GISOverviewResponse,
  GISFilterParams,
  ATMLocationItem,
  AlertItem,
  AlertSyncResponse,
  AlertChannelsStatusResponse,
  NotificationOutboxItem,
  AnalyticsOverview,
  DashboardSummary,
  AuditLogItem,
  ModelPerformanceData,
  BankActionItem,
  CreateBankActionPayload,
  ReleaseBankActionPayload,
  SandboxSimulatePayload,
  SystemStatus,
  EvidenceFileItem,
  EvidenceIntegrityResult,
  InvestigatorReportData,
  CaseHandoffItem,
  CreateHandoffPayload,
  OutcomeObservation,
  OutcomeCreatePayload,
  OutcomeCorrectPayload,
  OutcomeMetrics,
  RegionItem,
  GeographyCatalogItem,
  InterventionPlanItem,
  InterventionPlanActionItem,
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

// Interceptor for handling 401 Unauthorized vs 403 Forbidden
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 401 Unauthorized: Session invalid or expired, close session cleanly
      localStorage.removeItem('cybershield_token');
      localStorage.removeItem('cybershield_user');
      window.dispatchEvent(new CustomEvent('auth:expired', {
        detail: error.response?.data?.detail || 'Your session has expired. Please log in again.'
      }));
    } else if (error.response?.status === 403) {
      // 403 Forbidden: Authenticated user lacks required permission
      // Do NOT clear user session; dispatch notification event
      window.dispatchEvent(new CustomEvent('auth:forbidden', {
        detail: error.response?.data?.detail || 'Access forbidden: Insufficient role permissions.'
      }));
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

  // Health
  getHealth: async () => {
    const healthUrl = API_BASE_URL.replace(/\/api\/v1\/?$/, '') + '/health';
    const res = await axios.get(healthUrl);
    return res.data;
  },

  // Complaints
  getComplaints: async (params?: { fraud_type?: string; risk_level?: string; search?: string; limit?: number; skip?: number; state?: string; region_id?: string }) => {
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
    region_id?: string;
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
  runPrediction: async (complaintId: string | number, asOf?: string) => {
    const res = await apiClient.post<Prediction>(`/predictions/${complaintId}`, asOf ? { analysis_as_of: asOf } : {});
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
  getPredictionVersions: async (complaintId: string | number): Promise<PredictionVersionSummary[]> => {
    try {
      const res = await apiClient.get<PredictionVersionSummary[]>(`/predictions/${complaintId}/versions`);
      return Array.isArray(res.data) ? res.data : [];
    } catch (err: any) {
      if (err.response?.status === 404) {
        return [];
      }
      throw err;
    }
  },
  getPredictionVersion: async (predictionId: number): Promise<Prediction | null> => {
    try {
      const res = await apiClient.get<Prediction>(`/predictions/version/${predictionId}`);
      return res.data;
    } catch (err: any) {
      if (err.response?.status === 404) {
        return null;
      }
      throw err;
    }
  },
  getTransactions: async (complaintId: string | number, asOf?: string) => {
    const res = await apiClient.get<any>(`/complaints/${complaintId}/transactions`, {
      params: asOf ? { as_of: asOf } : undefined,
    });
    return res.data;
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
  getGraph: async (complaintId: string | number, asOf?: string) => {
    const res = await apiClient.get<GraphData>(`/complaints/${complaintId}/graph`, {
      params: asOf ? { as_of: asOf } : undefined,
    });
    return res.data;
  },

  // GIS
  getRiskMap: async (params?: GISFilterParams) => {
    const res = await apiClient.get<GISOverviewResponse>('/risk-map', { params });
    return res.data;
  },
  getClusters: async (params?: GISFilterParams) => {
    const res = await apiClient.get<HotspotCluster[]>('/clusters', { params });
    return res.data;
  },

  // Geography & Regions
  getRegions: async (includeInactive = false) => {
    const res = await apiClient.get<RegionItem[]>('/geography/regions', {
      params: { include_inactive: includeInactive },
    });
    return res.data;
  },
  getRegion: async (id: string) => {
    const res = await apiClient.get<RegionItem>(`/geography/regions/${id}`);
    return res.data;
  },
  getRegionClusters: async (id: string) => {
    const res = await apiClient.get<HotspotCluster[]>(`/geography/regions/${id}/clusters`);
    return res.data;
  },
  getGeographyCatalogs: async (regionId?: string) => {
    const res = await apiClient.get<GeographyCatalogItem[]>('/geography/catalogs', {
      params: regionId ? { region_id: regionId } : undefined,
    });
    return res.data;
  },
  validateCatalog: async (payload: any) => {
    const res = await apiClient.post<any>('/geography/validate', payload);
    return res.data;
  },
  importCatalog: async (payload: any) => {
    const res = await apiClient.post<any>('/geography/import', payload);
    return res.data;
  },

  // Alerts
  getAlerts: async (params?: { status?: string; severity?: string }) => {
    const res = await apiClient.get<AlertItem[]>('/alerts', { params });
    return res.data;
  },
  syncAlerts: async (params?: { since_id?: number; since_time?: string; limit?: number }) => {
    const res = await apiClient.get<AlertSyncResponse>('/alerts/sync', { params });
    return res.data;
  },
  getAlertChannelsStatus: async () => {
    const res = await apiClient.get<AlertChannelsStatusResponse>('/alerts/channels/status');
    return res.data;
  },
  getAlertOutbox: async (alertId: number) => {
    const res = await apiClient.get<NotificationOutboxItem[]>(`/alerts/${alertId}/outbox`);
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

  // System Diagnostics (Truthful runtime status)
  getSystemStatus: async () => {
    const res = await apiClient.get<SystemStatus>('/system/status');
    return res.data;
  },

  // Evidence Documentation (Phase 6)
  getComplaintEvidence: async (complaintId: string | number, includeSuperseded: boolean = true) => {
    const res = await apiClient.get<EvidenceFileItem[]>(`/complaints/${complaintId}/evidence`, {
      params: { include_superseded: includeSuperseded },
    });
    return res.data;
  },
  uploadComplaintEvidence: async (complaintId: string | number, formData: FormData) => {
    const res = await apiClient.post<EvidenceFileItem>(`/complaints/${complaintId}/evidence`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  replaceComplaintEvidence: async (complaintId: string | number, evidenceId: number, formData: FormData) => {
    const res = await apiClient.post<EvidenceFileItem>(`/complaints/${complaintId}/evidence/${evidenceId}/replace`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  checkEvidenceIntegrity: async (evidenceId: number, complaintId?: string | number) => {
    const url = complaintId
      ? `/complaints/${complaintId}/evidence/${evidenceId}/integrity`
      : `/evidence/${evidenceId}/integrity`;
    const res = await apiClient.get<EvidenceIntegrityResult>(url);
    return res.data;
  },
  getEvidenceDownloadUrl: (evidenceId: number, complaintId?: string | number) => {
    const base = apiClient.defaults.baseURL || '/api/v1';
    return complaintId
      ? `${base}/complaints/${complaintId}/evidence/${evidenceId}/download`
      : `${base}/evidence/${evidenceId}/download`;
  },

  // Investigator Report & Dossier (Phase 6)
  getComplaintReport: async (complaintId: string | number) => {
    const res = await apiClient.get<InvestigatorReportData>(`/complaints/${complaintId}/report`);
    return res.data;
  },
  exportComplaintDossier: async (complaintId: string | number, format: string = 'html') => {
    const res = await apiClient.get<Blob>(
      `/complaints/${complaintId}/report/export`,
      {
        params: {
          format,
          download: true,
        },
        responseType: 'blob',
      }
    );
    return res;
  },
  getReportExportUrl: (complaintId: string | number, format: string = 'html', download: boolean = false) => {
    const base = apiClient.defaults.baseURL || '/api/v1';
    return `${base}/complaints/${complaintId}/report/export?format=${format}&download=${download}`;
  },

  // Cross-Jurisdiction Handoffs (Phase 7)
  createComplaintHandoff: async (complaintId: string | number, payload: CreateHandoffPayload) => {
    const res = await apiClient.post<CaseHandoffItem>(`/complaints/${complaintId}/handoffs`, payload);
    return res.data;
  },
  getComplaintHandoffs: async (complaintId: string | number) => {
    const res = await apiClient.get<CaseHandoffItem[]>(`/complaints/${complaintId}/handoffs`);
    return res.data;
  },
  getIncomingHandoffs: async (statusFilter?: string) => {
    const res = await apiClient.get<CaseHandoffItem[]>('/handoffs/incoming', {
      params: { status_filter: statusFilter },
    });
    return res.data;
  },
  getOutgoingHandoffs: async (statusFilter?: string) => {
    const res = await apiClient.get<CaseHandoffItem[]>('/handoffs/outgoing', {
      params: { status_filter: statusFilter },
    });
    return res.data;
  },
  getHandoffDetail: async (handoffId: number) => {
    const res = await apiClient.get<CaseHandoffItem>(`/handoffs/${handoffId}`);
    return res.data;
  },
  acceptHandoff: async (handoffId: number) => {
    const res = await apiClient.post<CaseHandoffItem>(`/handoffs/${handoffId}/accept`);
    return res.data;
  },
  rejectHandoff: async (handoffId: number, rejectionReason: string) => {
    const res = await apiClient.post<CaseHandoffItem>(`/handoffs/${handoffId}/reject`, {
      rejection_reason: rejectionReason,
    });
    return res.data;
  },
  startHandoff: async (handoffId: number) => {
    const res = await apiClient.post<CaseHandoffItem>(`/handoffs/${handoffId}/start`);
    return res.data;
  },
  completeHandoff: async (handoffId: number, completedNotes?: string) => {
    const res = await apiClient.post<CaseHandoffItem>(`/handoffs/${handoffId}/complete`, {
      completed_notes: completedNotes,
    });
    return res.data;
  },
  cancelHandoff: async (handoffId: number, cancellationReason: string) => {
    const res = await apiClient.post<CaseHandoffItem>(`/handoffs/${handoffId}/cancel`, {
      cancellation_reason: cancellationReason,
    });
    return res.data;
  },

  // Bank Actions (Phase 8)
  getBankActions: async (params?: { status?: string; environment?: string; complaint_id?: number }) => {
    const res = await apiClient.get<BankActionItem[]>('/bank-actions', {
      params: {
        status_filter: params?.status,
        environment_filter: params?.environment,
        complaint_id: params?.complaint_id,
      },
    });
    return res.data;
  },
  getBankAction: async (id: number | string) => {
    const res = await apiClient.get<BankActionItem>(`/bank-actions/${id}`);
    return res.data;
  },
  createBankAction: async (payload: CreateBankActionPayload) => {
    const res = await apiClient.post<BankActionItem>('/bank-actions', payload);
    return res.data;
  },
  approveBankAction: async (id: number | string, notes?: string) => {
    const res = await apiClient.post<BankActionItem>(`/bank-actions/${id}/approve`, null, {
      params: notes ? { notes } : undefined,
    });
    return res.data;
  },
  dispatchBankAction: async (id: number | string) => {
    const res = await apiClient.post<BankActionItem>(`/bank-actions/${id}/dispatch`);
    return res.data;
  },
  releaseBankAction: async (id: number | string, payload: ReleaseBankActionPayload) => {
    const res = await apiClient.post<BankActionItem>(`/bank-actions/${id}/release`, payload);
    return res.data;
  },
  cancelBankAction: async (id: number | string, cancellationReason: string) => {
    const res = await apiClient.post<BankActionItem>(`/bank-actions/${id}/cancel`, null, {
      params: { cancellation_reason: cancellationReason },
    });
    return res.data;
  },
  sandboxSimulateBankAction: async (id: number | string, payload: SandboxSimulatePayload) => {
    const res = await apiClient.post<any>(`/bank-actions/${id}/sandbox-simulate`, payload);
    return res.data;
  },

  // ─── Phase 09: Outcome Observations ────────────────────────────────────────
  ingestOutcome: async (complaintId: number | string, payload: OutcomeCreatePayload) => {
    const res = await apiClient.post<OutcomeObservation>(`/outcomes/complaints/${complaintId}`, payload);
    return res.data;
  },
  correctOutcome: async (outcomeId: number | string, payload: OutcomeCorrectPayload) => {
    const res = await apiClient.post<OutcomeObservation>(`/outcomes/${outcomeId}/correct`, payload);
    return res.data;
  },
  listOutcomesForComplaint: async (complaintId: number | string, includeSuperseded = false) => {
    const res = await apiClient.get<OutcomeObservation[]>(`/outcomes/complaints/${complaintId}`, {
      params: { include_superseded: includeSuperseded },
    });
    return res.data;
  },
  getOutcome: async (outcomeId: number | string) => {
    const res = await apiClient.get<OutcomeObservation>(`/outcomes/${outcomeId}`);
    return res.data;
  },
  getOutcomeMetrics: async () => {
    const res = await apiClient.get<OutcomeMetrics>('/outcomes/metrics');
    return res.data;
  },

  // ─── Phase 3: Intervention Orchestrator ─────────────────────────────────────
  getInterventionPlan: async (complaintId: number | string) => {
    const res = await apiClient.get<InterventionPlanItem>(`/complaints/${complaintId}/intervention-plan`);
    return res.data;
  },
  generateInterventionPlan: async (complaintId: number | string) => {
    const res = await apiClient.post<InterventionPlanItem>(`/complaints/${complaintId}/intervention-plan`);
    return res.data;
  },
  updateInterventionActionStatus: async (planId: number, actionId: number, status: string, notes?: string) => {
    const res = await apiClient.patch<InterventionPlanActionItem>(`/intervention-plans/${planId}/actions/${actionId}`, {
      status,
      notes,
    });
    return res.data;
  },
  refreshInterventionPlan: async (planId: number) => {
    const res = await apiClient.post<InterventionPlanItem>(`/intervention-plans/${planId}/refresh`);
    return res.data;
  },
};
