import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, UserRole } from '../types';
import { api } from '../services/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, pass: string) => Promise<void>;
  demoLogin: (role: UserRole) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const DEMO_CREDENTIALS: Record<UserRole, { email: string; pass: string; title: string; desc: string }> = {
  I4C_ADMIN: {
    email: 'admin@cybershield.gov.in',
    pass: 'CyberAdmin@2026',
    title: 'I4C National Command',
    desc: 'National Cybercrime Coordination Centre oversight'
  },
  STATE_LEA: {
    email: 'state.lea@delhi.cyber.gov.in',
    pass: 'StateLea@2026',
    title: 'Delhi Cyber Crime Unit (NCT)',
    desc: 'State-level predictive policing and inter-district coordination'
  },
  DISTRICT_LEA: {
    email: 'district.lea@southdelhi.cyber.gov.in',
    pass: 'IndoreLea@2026',
    title: 'District Cyber Cell (South Delhi)',
    desc: 'Field interception & ATM rapid response unit'
  },
  BANK_OFFICER: {
    email: 'officer@sbi.co.in',
    pass: 'BankOfficer@2026',
    title: 'Bank Fraud Ops (SBI)',
    desc: 'ATM transaction freeze & account lien placement'
  },
  ANALYST: {
    email: 'analyst@cybershield.gov.in',
    pass: 'Analyst@2026',
    title: 'Senior Intelligence Analyst',
    desc: 'Graph intelligence & temporal pattern triage'
  },
  AUDITOR: {
    email: 'auditor@mha.gov.in',
    pass: 'Auditor@2026',
    title: 'MHA Compliance Auditor',
    desc: 'Chain of custody & algorithmic accountability review'
  }
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('cybershield_token'));
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('cybershield_token');
      const storedUser = localStorage.getItem('cybershield_user');
      if (storedToken && storedUser) {
        setToken(storedToken);
        try {
          setUser(JSON.parse(storedUser));
        } catch {
          localStorage.removeItem('cybershield_user');
        }
      }
      setLoading(false);
    };
    initAuth();

    const handleExpired = () => {
      setToken(null);
      setUser(null);
      sessionStorage.setItem('cybershield_session_expired', 'Your secure session has expired. Please sign in again.');
    };
    window.addEventListener('auth:expired', handleExpired);
    return () => window.removeEventListener('auth:expired', handleExpired);
  }, []);

  const login = async (email: string, pass: string) => {
    const res = await api.login(email, pass);
    setToken(res.access_token);
    setUser(res.user);
    localStorage.setItem('cybershield_token', res.access_token);
    localStorage.setItem('cybershield_user', JSON.stringify(res.user));
  };

  const demoLogin = async (role: UserRole) => {
    const creds = DEMO_CREDENTIALS[role];
    await login(creds.email, creds.pass);
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('cybershield_token');
    localStorage.removeItem('cybershield_user');
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        login,
        demoLogin,
        logout,
        loading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
