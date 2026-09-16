import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './store/authContext';
import { DashboardLayout } from './layouts/DashboardLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { RiskMap } from './pages/RiskMap';
import { Complaints } from './pages/Complaints';
import { CaseIntelligence } from './pages/CaseIntelligence';
import { TransactionNetwork } from './pages/TransactionNetwork';
import { AlertsCenter } from './pages/AlertsCenter';
import { Analytics } from './pages/Analytics';
import { ModelPerformance } from './pages/ModelPerformance';
import { AuditLog } from './pages/AuditLog';
import { Settings } from './pages/Settings';

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
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
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};
