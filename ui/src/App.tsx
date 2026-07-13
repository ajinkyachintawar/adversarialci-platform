import { BrowserRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom';

import { AuthProvider, useAuth } from './context/AuthContext';
import { LogoTile } from './components/design';
import Landing from './pages/Landing';
import About from './pages/About';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import VendorRegistry from './pages/VendorRegistry';
import CourtSessionWizard from './pages/CourtSessionWizard';
import ReportView from './pages/ReportView';
import IntelligenceTracker from './pages/IntelligenceTracker';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={<AppShell />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

function AppShell() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', background: 'var(--bg)' }}>
      <Sidebar />
      <div style={{ flex: 1, minWidth: 0, overflowX: 'hidden' }}>
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/vendors" element={<VendorRegistry />} />
          <Route path="/evaluate" element={<CourtSessionWizard />} />
          <Route path="/report/:id" element={<ReportView />} />
          <Route path="/history" element={<IntelligenceTracker />} />
        </Routes>
      </div>
    </div>
  );
}

const NAV_ITEMS: { path: string; label: string }[] = [
  { path: '/dashboard', label: 'Dashboard' },
  { path: '/vendors',   label: 'Vendor Registry' },
  { path: '/evaluate',  label: 'Run Evaluation' },
  { path: '/history',   label: 'History' },
];

function initials(email: string): string {
  const clean = email.trim();
  if (!clean) return '??';
  const parts = clean.split(/[@._-]/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return clean.slice(0, 2).toUpperCase();
}

function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { session, user, signOut } = useAuth();

  const isActive = (path: string) => location.pathname.startsWith(path);

  return (
    <aside style={{
      width: 232, flexShrink: 0,
      borderRight: '1px solid var(--line)',
      padding: '22px 16px',
      display: 'flex', flexDirection: 'column',
      position: 'sticky', top: 0, height: '100vh',
      boxSizing: 'border-box',
    }}>
      <div
        onClick={() => navigate('/')}
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '0 8px', marginBottom: 32, cursor: 'pointer',
        }}
      >
        <LogoTile size={28} />
        <span style={{ fontWeight: 700, fontSize: 15 }}>AdversarialCI</span>
      </div>

      {NAV_ITEMS.map(item => {
        const active = isActive(item.path);
        return (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'var(--surface-2)'; }}
            onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent'; }}
            style={{
              display: 'flex', alignItems: 'center',
              padding: '10px 12px', borderRadius: 8, border: 'none',
              background: active ? 'var(--accent-12)' : 'transparent',
              color: active ? 'var(--accent)' : 'oklch(0.78 0.006 260)',
              fontFamily: 'inherit', fontSize: 14, fontWeight: 600,
              cursor: 'pointer', textAlign: 'left', width: '100%',
              boxSizing: 'border-box', marginBottom: 2,
              transition: 'background 0.15s',
            }}
          >
            {item.label}
          </button>
        );
      })}

      <div style={{ marginTop: 'auto', paddingTop: 16, borderTop: '1px solid var(--line)' }}>
        {session && user ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 8, borderRadius: 9 }}>
            <div style={{
              width: 30, height: 30, borderRadius: '50%',
              background: 'var(--success)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, fontWeight: 700, color: 'var(--bg)', flexShrink: 0,
            }}>{initials(user.email || '')}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 13, fontWeight: 600,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{user.email}</div>
              <div
                onClick={() => { signOut(); navigate('/'); }}
                style={{ fontSize: 11, color: 'var(--text-3)', cursor: 'pointer' }}
              >
                Sign out
              </div>
            </div>
          </div>
        ) : (
          <button
            onClick={() => navigate('/login')}
            style={{
              width: '100%',
              background: 'var(--accent-12)',
              border: '1px solid var(--accent-30)',
              color: 'var(--accent)',
              padding: 9, borderRadius: 8,
              fontFamily: 'inherit', fontSize: 13, fontWeight: 700, cursor: 'pointer',
            }}
          >
            Sign in
          </button>
        )}
      </div>
    </aside>
  );
}

export default App;
