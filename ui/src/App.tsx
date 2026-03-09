import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { clsx } from 'clsx';
import { Shield, LayoutDashboard, Database, Scale, Clock } from 'lucide-react';
import './App.css';

import Dashboard from './pages/Dashboard';
import VendorRegistry from './pages/VendorRegistry';
import CourtSessionWizard from './pages/CourtSessionWizard';
import ReportView from './pages/ReportView';
import IntelligenceTracker from './pages/IntelligenceTracker';

function App() {
  return (
    <BrowserRouter>
      <div className="app-container">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/vendors" element={<VendorRegistry />} />
            <Route path="/evaluate" element={<CourtSessionWizard />} />
            <Route path="/report/:id" element={<ReportView />} />
            <Route path="/history" element={<IntelligenceTracker />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

function Sidebar() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Overview', icon: LayoutDashboard },
    { path: '/vendors', label: 'Vendor Registry', icon: Database },
    { path: '/evaluate', label: 'Court Session', icon: Scale },
    { path: '/history', label: 'History', icon: Clock },
  ];

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <aside className="sidebar glass-panel">
      <div className="sidebar-header">
        <Shield className="logo-icon" size={24} />
        <h1 className="logo-text">ADVERSARIAL<span>CI</span></h1>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={clsx('nav-link', isActive(item.path) && 'active')}
          >
            <item.icon size={17} />
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>

      <div className="sidebar-footer terminal-text">
        <div className="status-indicator">
          <span className="dot" />
          SYSTEM ONLINE
        </div>
      </div>
    </aside>
  );
}

export default App;
