import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './store/authContext';
import { DashboardLayout } from './layouts/DashboardLayout';
import { ProtectedRoute } from './components/ProtectedRoute';

// Route-level code splitting via React.lazy
const Login = React.lazy(() => import('./pages/Login').then(m => ({ default: m.Login })));
const Dashboard = React.lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const RiskMap = React.lazy(() => import('./pages/RiskMap').then(m => ({ default: m.RiskMap })));
const Complaints = React.lazy(() => import('./pages/Complaints').then(m => ({ default: m.Complaints })));
const CaseIntelligence = React.lazy(() => import('./pages/CaseIntelligence').then(m => ({ default: m.CaseIntelligence })));
const TransactionNetwork = React.lazy(() => import('./pages/TransactionNetwork').then(m => ({ default: m.TransactionNetwork })));
const AlertsCenter = React.lazy(() => import('./pages/AlertsCenter').then(m => ({ default: m.AlertsCenter })));
const Analytics = React.lazy(() => import('./pages/Analytics').then(m => ({ default: m.Analytics })));
const ModelPerformance = React.lazy(() => import('./pages/ModelPerformance').then(m => ({ default: m.ModelPerformance })));
const AuditLog = React.lazy(() => import('./pages/AuditLog').then(m => ({ default: m.AuditLog })));
const Settings = React.lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const OutcomeMetrics = React.lazy(() => import('./pages/OutcomeMetrics').then(m => ({ default: m.OutcomeMetrics })));

const PageLoading: React.FC = () => (
  <div className="flex min-h-[50vh] items-center justify-center">
    <div className="flex flex-col items-center gap-3">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
      <span className="text-xs font-mono text-slate-400">Loading component...</span>
    </div>
  </div>
);

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<PageLoading />}>
          <Routes>
            <Route path="/login" element={<Login />} />

            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route
                path="risk-map"
                element={
                  <ProtectedRoute allowedRoles={['I4C_ADMIN', 'STATE_LEA', 'DISTRICT_LEA', 'ANALYST']}>
                    <RiskMap />
                  </ProtectedRoute>
                }
              />
              <Route path="complaints" element={<Complaints />} />
              <Route path="cases/:id" element={<CaseIntelligence />} />
              <Route path="network/:complaintId" element={<TransactionNetwork />} />
              <Route
                path="alerts"
                element={
                  <ProtectedRoute allowedRoles={['I4C_ADMIN', 'STATE_LEA', 'DISTRICT_LEA', 'BANK_OFFICER']}>
                    <AlertsCenter />
                  </ProtectedRoute>
                }
              />
              <Route
                path="analytics"
                element={
                  <ProtectedRoute allowedRoles={['I4C_ADMIN', 'STATE_LEA', 'DISTRICT_LEA', 'ANALYST']}>
                    <Analytics />
                  </ProtectedRoute>
                }
              />
              <Route
                path="model-performance"
                element={
                  <ProtectedRoute allowedRoles={['I4C_ADMIN', 'ANALYST', 'AUDITOR', 'STATE_LEA', 'DISTRICT_LEA']}>
                    <ModelPerformance />
                  </ProtectedRoute>
                }
              />
              <Route
                path="audit"
                element={
                  <ProtectedRoute allowedRoles={['I4C_ADMIN', 'AUDITOR']}>
                    <AuditLog />
                  </ProtectedRoute>
                }
              />
              <Route path="settings" element={<Settings />} />
              <Route
                path="outcome-metrics"
                element={
                  <ProtectedRoute allowedRoles={['I4C_ADMIN', 'STATE_LEA', 'DISTRICT_LEA', 'ANALYST', 'AUDITOR']}>
                    <OutcomeMetrics />
                  </ProtectedRoute>
                }
              />
            </Route>

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
};
