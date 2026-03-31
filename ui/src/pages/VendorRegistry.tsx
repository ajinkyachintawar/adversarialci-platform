import { useState, Fragment, useRef } from 'react';
import { Plus, CheckCircle2, Search, RefreshCw, ChevronDown, ChevronRight, Database, ExternalLink, Github, Rss, AlertTriangle, Clock, FileText, Trash2, X, Loader2 } from 'lucide-react';
import Skeleton from '../components/Skeleton';
import ErrorState from '../components/ErrorState';
import { useAllVendors } from '../hooks/useApi';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const ADMIN_KEY = import.meta.env.VITE_ADMIN_KEY || '';

const ADMIN_MODE = true; // Set true only for local development

interface AtlasData {
    research_count: number;
    sources: Record<string, number>;
    last_scraped: string | null;
    status: string;
}

interface EnrichedVendor {
    name: string;
    vertical: string;
    pricing_url: string | null;
    github_repo: string | null;
    blog_rss: string[];
    blog_tavily: string[];
    migration_queries: string[];
    complaint_queries: string[];
    added_at: string;
    added_by: string;
    atlas: AtlasData | null;
}

export default function VendorRegistry() {
    const [searchTerm, setSearchTerm] = useState('');
    const [activeVertical, setActiveVertical] = useState<string>('all');
    const [expandedVendor, setExpandedVendor] = useState<string | null>(null);

    const { data: vendorData, isLoading: loading, error: queryError, refetch: fetchVendors } = useAllVendors();
    const vendors: EnrichedVendor[] = vendorData ? [...(vendorData.database || []), ...(vendorData.cloud || []), ...(vendorData.crm || [])] : [];
    const error = queryError ? 'Failed to load vendor data.' : '';



    // CRUD state
    const [showAddModal, setShowAddModal] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<{ name: string; vertical: string } | null>(null);

    // Per-vendor refresh progress
    interface RefreshState {
        currentSource: string;
        completedSources: number;
        totalSources: number;
        done: boolean;
    }
    const [refreshStates, setRefreshStates] = useState<Record<string, RefreshState>>({});

    // Bulk refresh state
    interface BulkRefreshState {
        isRefreshing: boolean;
        currentVendor: string | null;
        completedCount: number;
        totalCount: number;
    }
    const [bulkRefresh, setBulkRefresh] = useState<BulkRefreshState>({ isRefreshing: false, currentVendor: null, completedCount: 0, totalCount: 0 });
    const cancelledRef = useRef(false);

    const handleDelete = async (name: string, vertical: string) => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/vendors`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY },
                body: JSON.stringify({ name, vertical }),
            });
            if (res.ok) {
                setDeleteTarget(null);
                setExpandedVendor(null);
                fetchVendors();
            }
        } catch (e) {
            console.error("Delete failed:", e);
        }
    };

    const REFRESH_SOURCES = ['Tavily', 'HN', 'Pricing', 'GitHub', 'Blog', 'Migration'];

    const handleRefresh = (name: string, vertical: string) => {
        setRefreshStates(prev => ({
            ...prev,
            [name]: { currentSource: 'Connecting...', completedSources: 0, totalSources: REFRESH_SOURCES.length, done: false }
        }));

        fetch(`${API_BASE_URL}/api/vendors/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY },
            body: JSON.stringify({ name, vertical }),
        }).then(async (response) => {
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            if (!reader) return;

            let buffer = '';
            let completed = 0;
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                for (const line of lines) {
                    if (!line.startsWith('data:')) continue;
                    const data = line.substring(5).trim();
                    if (data === 'keep-alive') continue;

                    if (data.startsWith('__REFRESH_DONE__:')) {
                        setRefreshStates(prev => ({ ...prev, [name]: { ...prev[name], done: true, currentSource: 'Complete!', completedSources: REFRESH_SOURCES.length } }));
                        setTimeout(() => {
                            setRefreshStates(prev => { const next = { ...prev }; delete next[name]; return next; });
                            fetchVendors();
                        }, 2000);
                        return;
                    }

                    // Detect source completion: "✅ Tavily:", "✅ HN:", etc.
                    const doneMatch = data.match(/✅\s*(Tavily|HN|Pricing|GitHub|Blog|Migration):/i);
                    if (doneMatch) {
                        completed++;
                        const nextIdx = completed < REFRESH_SOURCES.length ? completed : completed - 1;
                        setRefreshStates(prev => ({
                            ...prev,
                            [name]: { ...prev[name], completedSources: completed, currentSource: completed < REFRESH_SOURCES.length ? REFRESH_SOURCES[nextIdx] : 'Finishing...' }
                        }));
                        continue;
                    }

                    // Detect source starting via keywords
                    for (const src of REFRESH_SOURCES) {
                        if (data.toLowerCase().includes(src.toLowerCase()) && !data.includes('✅')) {
                            setRefreshStates(prev => ({ ...prev, [name]: { ...prev[name], currentSource: src } }));
                            break;
                        }
                    }
                }
            }
        }).catch((err) => {
            if (err.name !== 'AbortError') {
                setRefreshStates(prev => ({ ...prev, [name]: { ...prev[name], currentSource: `Error: ${err.message}`, done: true } }));
                setTimeout(() => {
                    setRefreshStates(prev => { const next = { ...prev }; delete next[name]; return next; });
                }, 3000);
            }
        });
    };

    /** Promise-based single-vendor refresh for use in bulk refresh */
    const refreshVendorAsync = (name: string, vertical: string): Promise<void> => {
        return new Promise<void>((resolve) => {
            setRefreshStates(prev => ({
                ...prev,
                [name]: { currentSource: 'Connecting...', completedSources: 0, totalSources: REFRESH_SOURCES.length, done: false }
            }));

            fetch(`${API_BASE_URL}/api/vendors/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY },
                body: JSON.stringify({ name, vertical }),
            }).then(async (response) => {
                const reader = response.body?.getReader();
                const decoder = new TextDecoder();
                if (!reader) { resolve(); return; }

                let buffer = '';
                let completed = 0;
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';
                    for (const line of lines) {
                        if (!line.startsWith('data:')) continue;
                        const data = line.substring(5).trim();
                        if (data === 'keep-alive') continue;

                        if (data.startsWith('__REFRESH_DONE__:')) {
                            setRefreshStates(prev => ({ ...prev, [name]: { ...prev[name], done: true, currentSource: 'Complete!', completedSources: REFRESH_SOURCES.length } }));
                            setTimeout(() => {
                                setRefreshStates(prev => { const next = { ...prev }; delete next[name]; return next; });
                            }, 1500);
                            resolve();
                            return;
                        }

                        const doneMatch = data.match(/✅\s*(Tavily|HN|Pricing|GitHub|Blog|Migration):/i);
                        if (doneMatch) {
                            completed++;
                            const nextIdx = completed < REFRESH_SOURCES.length ? completed : completed - 1;
                            setRefreshStates(prev => ({
                                ...prev,
                                [name]: { ...prev[name], completedSources: completed, currentSource: completed < REFRESH_SOURCES.length ? REFRESH_SOURCES[nextIdx] : 'Finishing...' }
                            }));
                            continue;
                        }

                        for (const src of REFRESH_SOURCES) {
                            if (data.toLowerCase().includes(src.toLowerCase()) && !data.includes('✅')) {
                                setRefreshStates(prev => ({ ...prev, [name]: { ...prev[name], currentSource: src } }));
                                break;
                            }
                        }
                    }
                }
                resolve();
            }).catch(() => { resolve(); });
        });
    };

    const handleRefreshAll = async () => {
        const vendorsToRefresh = filteredVendors;
        if (vendorsToRefresh.length === 0) return;

        cancelledRef.current = false;
        setBulkRefresh({ isRefreshing: true, currentVendor: null, completedCount: 0, totalCount: vendorsToRefresh.length });

        for (const vendor of vendorsToRefresh) {
            if (cancelledRef.current) break;
            setBulkRefresh(prev => ({ ...prev, currentVendor: vendor.name }));
            await refreshVendorAsync(vendor.name, vendor.vertical);
            setBulkRefresh(prev => ({ ...prev, completedCount: prev.completedCount + 1 }));
        }

        setBulkRefresh(prev => ({ ...prev, isRefreshing: false, currentVendor: null }));
        fetchVendors();
    };

    const handleCancelBulk = () => {
        cancelledRef.current = true;
    };

    const filteredVendors = vendors.filter(v => {
        const matchesSearch = v.name.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesVertical = activeVertical === 'all' || v.vertical === activeVertical;
        return matchesSearch && matchesVertical;
    });

    const totalResearch = vendors.reduce((sum, v) => sum + (v.atlas?.research_count || 0), 0);
    const freshCount = vendors.filter(v => v.atlas?.status === 'fresh').length;
    const staleCount = vendors.filter(v => v.atlas?.status === 'stale' || v.atlas?.status === 'new').length;

    const getStatusInfo = (status: string | undefined) => {
        switch (status) {
            case 'fresh': return { dotClass: 'fresh', label: 'Fresh' };
            case 'stale': return { dotClass: 'stale', label: 'Stale' };
            case 'new': return { dotClass: 'new', label: 'New' };
            default: return { dotClass: 'none', label: 'No Data' };
        }
    };

    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return 'Never';
        try {
            const d = new Date(dateStr);
            const now = new Date();
            const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
            if (diffDays === 0) return 'Today';
            if (diffDays === 1) return 'Yesterday';
            if (diffDays < 30) return `${diffDays}d ago`;
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        } catch {
            return dateStr;
        }
    };

    if (error) {
        return (
            <div className="animate-fade-in">
                <div className="page-header"><h1>Vendor Registry</h1></div>
                <ErrorState message={error} onRetry={fetchVendors} />
            </div>
        );
    }

    return (
        <div className="animate-fade-in">
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--sp-6)' }}>
                <div className="page-header" style={{ marginBottom: 0 }}>
                    <h1>Vendor Registry</h1>
                    <p>Central intelligence database of monitored competitors.</p>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                    {ADMIN_MODE && (
                        <button
                            onClick={bulkRefresh.isRefreshing ? handleCancelBulk : handleRefreshAll}
                            disabled={loading}
                            style={{
                                display: 'flex', alignItems: 'center', gap: '6px',
                                padding: '8px 16px', borderRadius: '6px', fontSize: '13px',
                                cursor: loading ? 'not-allowed' : 'pointer',
                                background: 'transparent',
                                border: `1px solid ${bulkRefresh.isRefreshing ? '#ff4466' : '#00d4ff'}`,
                                color: bulkRefresh.isRefreshing ? '#ff4466' : '#00d4ff',
                                transition: 'all 0.2s ease'
                            }}
                        >
                            {bulkRefresh.isRefreshing ? (
                                <><X size={14} /> Cancel</>
                            ) : (
                                <><RefreshCw size={14} /> Refresh All</>
                            )}
                        </button>
                    )}
                    {ADMIN_MODE && (
                        <button className="btn btn-solid" onClick={() => setShowAddModal(true)}>
                            <Plus size={15} /> Add Vendor
                        </button>
                    )}
                </div>
            </div>

            {/* KPI Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--sp-3)', marginBottom: 'var(--sp-6)' }}>
                {loading ? (
                    Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} className="glass-panel kpi-card"><Skeleton width={100} height={40} /></div>
                    ))
                ) : (
                    [
                        { label: 'Total Vendors', value: vendors.length, icon: <Database size={16} />, color: 'var(--accent-cyan)', bg: 'var(--accent-cyan-muted)' },
                        { label: 'Intel Documents', value: totalResearch, icon: <FileText size={16} />, color: 'var(--accent-purple)', bg: 'var(--accent-purple-muted)' },
                        { label: 'Fresh', value: freshCount, icon: <CheckCircle2 size={16} />, color: 'var(--accent-green)', bg: 'var(--accent-green-muted)' },
                        { label: 'Needs Refresh', value: staleCount, icon: <AlertTriangle size={16} />, color: 'var(--accent-yellow)', bg: 'var(--accent-yellow-muted)' },
                    ].map((stat, i) => (
                        <div key={i} className="glass-panel kpi-card">
                            <div className="kpi-icon" style={{ background: stat.bg, color: stat.color }}>{stat.icon}</div>
                            <div>
                                <div className="kpi-value" style={{ color: stat.color, fontSize: 'var(--text-lg)' }}>{stat.value}</div>
                                <div className="kpi-label">{stat.label}</div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Controls */}
            <div style={{ display: 'flex', gap: 'var(--sp-3)', marginBottom: 'var(--sp-4)', flexWrap: 'wrap' }}>
                <div style={{ position: 'relative', flexGrow: 1, maxWidth: 380 }}>
                    <Search size={16} style={{ position: 'absolute', left: '0.8rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                    <input type="text" className="input-field" placeholder="Search vendors..." style={{ paddingLeft: '2.2rem' }} value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} />
                </div>
                <div style={{ display: 'flex', gap: 'var(--sp-1)', background: 'var(--bg-surface)', padding: '3px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
                    {['all', 'database', 'cloud', 'crm'].map(v => (
                        <button key={v} onClick={() => setActiveVertical(v)} style={{
                            padding: '0.35rem 0.9rem', borderRadius: 'var(--radius-sm)',
                            color: activeVertical === v ? 'var(--bg-base)' : 'var(--text-secondary)',
                            backgroundColor: activeVertical === v ? 'var(--accent-cyan)' : 'transparent',
                            fontWeight: activeVertical === v ? 600 : 400,
                            fontSize: 'var(--text-sm)',
                            textTransform: 'capitalize', transition: 'all 0.2s',
                        }}>{v}</button>
                    ))}
                </div>
            </div>

            {/* Bulk Refresh Progress Banner */}
            {bulkRefresh.isRefreshing && (
                <div style={{
                    display: 'flex', alignItems: 'center', gap: '16px',
                    padding: '12px 16px', marginBottom: 'var(--sp-4)',
                    background: 'rgba(0, 212, 255, 0.06)',
                    border: '1px solid rgba(0, 212, 255, 0.15)',
                    borderRadius: '8px'
                }}>
                    <Loader2 size={16} className="animate-spin" style={{ color: '#00d4ff', flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
                            <span style={{ fontSize: '13px', color: '#ffffff' }}>
                                Refreshing {activeVertical === 'all' ? 'all' : activeVertical} vendors...
                            </span>
                            <span style={{ fontSize: '12px', color: '#8a8a9a' }}>
                                {bulkRefresh.completedCount}/{bulkRefresh.totalCount}
                            </span>
                            {bulkRefresh.currentVendor && (
                                <span style={{ fontSize: '12px', color: '#00d4ff' }}>
                                    Currently: {bulkRefresh.currentVendor}
                                </span>
                            )}
                        </div>
                        <div style={{ width: '100%', height: '6px', background: '#1a1a24', borderRadius: '3px', overflow: 'hidden' }}>
                            <div style={{
                                width: bulkRefresh.totalCount > 0 ? `${(bulkRefresh.completedCount / bulkRefresh.totalCount) * 100}%` : '0%',
                                height: '100%', background: '#00d4ff',
                                transition: 'width 0.5s ease'
                            }} />
                        </div>
                    </div>
                    <button
                        onClick={handleCancelBulk}
                        style={{
                            padding: '4px 12px', fontSize: '12px', borderRadius: '4px',
                            background: 'transparent', border: '1px solid #ff4466',
                            color: '#ff4466', cursor: 'pointer', flexShrink: 0
                        }}
                    >
                        Cancel
                    </button>
                </div>
            )}

            {/* Table */}
            <div className="glass-panel" style={{ overflow: 'hidden' }}>
                <table className="data-table">
                    <thead>
                        <tr>
                            <th style={{ width: 36, padding: '0.7rem 0.5rem 0.7rem 1rem' }}></th>
                            <th>Vendor</th>
                            <th>Vertical</th>
                            <th style={{ textAlign: 'center' }}>Status</th>
                            <th style={{ textAlign: 'center' }}>Research</th>
                            <th style={{ textAlign: 'center' }}>Sources</th>
                            <th style={{ textAlign: 'center' }}>Last Scraped</th>
                            <th style={{ textAlign: 'right', paddingRight: '1rem' }}>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading && (
                            Array.from({ length: 5 }).map((_, i) => (
                                <tr key={i}><td colSpan={8} style={{ padding: '0.5rem 1rem' }}><Skeleton height={24} /></td></tr>
                            ))
                        )}
                        {filteredVendors.map((vendor, idx) => {
                            const isExpanded = expandedVendor === vendor.name;
                            const status = getStatusInfo(vendor.atlas?.status);
                            const sourcesActive = vendor.atlas?.sources ? Object.values(vendor.atlas.sources).filter(c => c > 0).length : 0;
                            const rState = refreshStates[vendor.name];
                            const isRefreshing = !!rState && !rState.done;

                            return (
                                <Fragment key={idx}>
                                    <tr
                                        onClick={() => !isRefreshing && setExpandedVendor(isExpanded ? null : vendor.name)}
                                        style={{
                                            cursor: isRefreshing ? 'default' : 'pointer',
                                            borderBottom: isExpanded ? 'none' : undefined,
                                        }}
                                    >
                                        <td style={{ padding: '0.7rem 0.5rem 0.7rem 1rem', color: 'var(--text-muted)' }}>
                                            {isRefreshing ? <Loader2 size={14} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} /> : isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                        </td>
                                        <td style={{ fontWeight: 600 }}>{vendor.name}</td>
                                        <td><span className="chip">{vendor.vertical}</span></td>
                                        <td style={{ textAlign: 'center' }}>
                                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--sp-2)' }}>
                                                <span className={`status-dot ${status.dotClass}`} />
                                                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                                                    {isRefreshing ? 'Refreshing...' : status.label}
                                                </span>
                                            </div>
                                        </td>
                                        <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)', color: vendor.atlas?.research_count ? 'var(--accent-cyan)' : 'var(--text-muted)' }}>
                                            {vendor.atlas?.research_count || 0}
                                        </td>
                                        <td style={{ textAlign: 'center', fontSize: 'var(--text-sm)' }}>
                                            <span style={{ color: sourcesActive > 0 ? 'var(--accent-green)' : 'var(--text-muted)' }}>{sourcesActive}/7</span>
                                        </td>
                                        <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                                            {formatDate(vendor.atlas?.last_scraped || null)}
                                        </td>
                                        <td style={{ textAlign: 'right', paddingRight: '1rem' }} onClick={e => e.stopPropagation()}>
                                            <div style={{ display: 'flex', gap: 'var(--sp-1)', justifyContent: 'flex-end' }}>
                                                {ADMIN_MODE && (
                                                    <button
                                                        onClick={() => !isRefreshing && handleRefresh(vendor.name, vendor.vertical)}
                                                        disabled={isRefreshing}
                                                        title="Refresh intel"
                                                        className="btn btn-secondary"
                                                        style={{ padding: '0.3rem', color: isRefreshing ? 'var(--text-muted)' : 'var(--accent-cyan)' }}
                                                    >
                                                        <RefreshCw size={13} className={isRefreshing ? 'animate-spin' : ''} />
                                                    </button>
                                                )}
                                                {ADMIN_MODE && (
                                                    <button
                                                        onClick={() => setDeleteTarget({ name: vendor.name, vertical: vendor.vertical })}
                                                        title="Delete vendor"
                                                        className="btn btn-secondary"
                                                        style={{ padding: '0.3rem', color: 'var(--accent-red)' }}
                                                    >
                                                        <Trash2 size={13} />
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>

                                    {/* Inline Refresh Progress */}
                                    {rState && (
                                        <tr style={{ borderBottom: 'none' }}>
                                            <td colSpan={8} style={{ padding: '4px 1rem 8px 3rem' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                                    {rState.done ? (
                                                        <CheckCircle2 size={14} style={{ color: 'var(--accent-green)', flexShrink: 0 }} />
                                                    ) : (
                                                        <Loader2 size={14} className="animate-spin" style={{ color: 'var(--accent-cyan)', flexShrink: 0 }} />
                                                    )}
                                                    <div style={{
                                                        width: '120px', height: '6px',
                                                        background: '#1a1a24', borderRadius: '3px',
                                                        overflow: 'hidden', flexShrink: 0
                                                    }}>
                                                        <div style={{
                                                            width: `${(rState.completedSources / rState.totalSources) * 100}%`,
                                                            height: '100%',
                                                            background: rState.done ? 'var(--accent-green)' : 'var(--accent-cyan)',
                                                            transition: 'width 0.3s ease'
                                                        }} />
                                                    </div>
                                                    <span style={{ fontSize: '12px', color: '#8a8a9a', flexShrink: 0 }}>
                                                        {rState.completedSources}/{rState.totalSources} sources
                                                    </span>
                                                    <span style={{ fontSize: '12px', color: rState.done ? 'var(--accent-green)' : 'var(--accent-cyan)' }}>
                                                        {rState.done ? '✅ Complete!' : `Scraping: ${rState.currentSource}...`}
                                                    </span>
                                                </div>
                                            </td>
                                        </tr>
                                    )}

                                    {/* Expanded Detail */}
                                    {isExpanded && !isRefreshing && (
                                        <tr>
                                            <td colSpan={8} style={{ padding: '0 1rem 1.25rem 3rem', background: 'rgba(0,212,255,0.015)' }}>
                                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-6)', marginTop: 'var(--sp-2)' }}>
                                                    {/* Left: Sources */}
                                                    <div>
                                                        <div className="section-title">Intelligence Sources</div>
                                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
                                                            <SourceRow icon={<ExternalLink size={13} />} label="Pricing" value={vendor.pricing_url} isLink />
                                                            <SourceRow icon={<Github size={13} />} label="GitHub" value={vendor.github_repo ? `github.com/${vendor.github_repo}` : null} isLink />
                                                            <SourceRow icon={<Rss size={13} />} label="Blog RSS" value={vendor.blog_rss?.length ? `${vendor.blog_rss.length} feed(s)` : null} />
                                                            <SourceRow icon={<Search size={13} />} label="Blog Tavily" value={vendor.blog_tavily?.length ? `${vendor.blog_tavily.length} query(s)` : null} />
                                                        </div>

                                                        {vendor.migration_queries?.length > 0 && (
                                                            <div style={{ marginTop: 'var(--sp-4)' }}>
                                                                <div className="section-title">Migration Tracking</div>
                                                                {vendor.migration_queries.map((q, qi) => (
                                                                    <div key={qi} style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', padding: '0.2rem 0', borderLeft: '2px solid var(--accent-yellow)', paddingLeft: 'var(--sp-3)', marginBottom: 'var(--sp-1)' }}>{q}</div>
                                                                ))}
                                                            </div>
                                                        )}

                                                        {vendor.complaint_queries?.length > 0 && (
                                                            <div style={{ marginTop: 'var(--sp-4)' }}>
                                                                <div className="section-title" style={{ color: 'var(--accent-red)' }}>Complaint Monitoring</div>
                                                                {vendor.complaint_queries.map((q, qi) => (
                                                                    <div key={qi} style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', padding: '0.2rem 0', borderLeft: '2px solid var(--accent-red)', paddingLeft: 'var(--sp-3)', marginBottom: 'var(--sp-1)' }}>{q}</div>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>

                                                    {/* Right: Atlas Stats */}
                                                    <div>
                                                        <div className="section-title">Atlas Research Data</div>
                                                        {vendor.atlas ? (
                                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
                                                                {Object.entries(vendor.atlas.sources).map(([src, count]) => (
                                                                    <div key={src} style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
                                                                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', minWidth: 72, textTransform: 'capitalize' }}>{src}</span>
                                                                        <div className="progress-bar" style={{ flex: 1 }}>
                                                                            <div
                                                                                className="progress-fill"
                                                                                style={{
                                                                                    width: count > 0 ? `${Math.min(100, count * 10)}%` : '0%',
                                                                                    background: count > 0 ? 'var(--accent-cyan)' : 'transparent',
                                                                                }}
                                                                            />
                                                                        </div>
                                                                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: count > 0 ? 'var(--accent-cyan)' : 'var(--text-muted)', minWidth: 24, textAlign: 'right' }}>{count}</span>
                                                                    </div>
                                                                ))}
                                                                <div style={{
                                                                    display: 'flex', alignItems: 'center', gap: 'var(--sp-2)',
                                                                    marginTop: 'var(--sp-3)', padding: 'var(--sp-3)',
                                                                    background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-sm)',
                                                                }}>
                                                                    <Clock size={13} style={{ color: 'var(--text-muted)' }} />
                                                                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Last scraped: {formatDate(vendor.atlas.last_scraped)}</span>
                                                                </div>
                                                            </div>
                                                        ) : (
                                                            <div style={{
                                                                padding: 'var(--sp-5)', border: '1px dashed var(--border)',
                                                                borderRadius: 'var(--radius-md)', textAlign: 'center',
                                                                color: 'var(--text-muted)', fontSize: 'var(--text-sm)',
                                                            }}>
                                                                No Atlas data. Click <RefreshCw size={11} style={{ display: 'inline', verticalAlign: 'middle' }} /> to scrape.
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>

                                                {/* Actions at bottom */}
                                                <div style={{
                                                    display: 'flex', gap: 'var(--sp-2)', justifyContent: 'flex-end',
                                                    marginTop: 'var(--sp-4)', paddingTop: 'var(--sp-4)',
                                                    borderTop: '1px solid var(--border-subtle)',
                                                }}>
                                                    {ADMIN_MODE && (
                                                        <button className="btn btn-primary" style={{ fontSize: 'var(--text-xs)' }} onClick={(e) => { e.stopPropagation(); handleRefresh(vendor.name, vendor.vertical); }}>
                                                            <RefreshCw size={12} /> Refresh Data
                                                        </button>
                                                    )}
                                                    {ADMIN_MODE && (
                                                        <button className="btn btn-danger" style={{ fontSize: 'var(--text-xs)' }} onClick={(e) => { e.stopPropagation(); setDeleteTarget({ name: vendor.name, vertical: vendor.vertical }); }}>
                                                            <Trash2 size={12} /> Delete
                                                        </button>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                </Fragment>
                            );
                        })}
                        {filteredVendors.length === 0 && !loading && (
                            <tr><td colSpan={8} style={{ padding: 'var(--sp-12)', textAlign: 'center', color: 'var(--text-muted)' }}>No vendors found matching your criteria.</td></tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Add Modal */}
            {showAddModal && <AddVendorModal onClose={() => setShowAddModal(false)} onSuccess={() => { setShowAddModal(false); fetchVendors(); }} />}

            {/* Delete Modal */}
            {deleteTarget && (
                <div className="modal-overlay" onClick={() => setDeleteTarget(null)}>
                    <div className="modal-content" style={{ maxWidth: 440 }} onClick={e => e.stopPropagation()}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-5)' }}>
                            <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--accent-red)' }}>⚠️ Delete Vendor</h2>
                            <button onClick={() => setDeleteTarget(null)} style={{ color: 'var(--text-muted)' }}><X size={18} /></button>
                        </div>
                        <p style={{ color: 'var(--text-secondary)', marginBottom: 'var(--sp-2)', lineHeight: 1.6, fontSize: 'var(--text-sm)' }}>
                            Delete <strong style={{ color: 'var(--text-primary)' }}>{deleteTarget.name}</strong> from the <strong>{deleteTarget.vertical}</strong> vertical?
                        </p>
                        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-xs)', marginBottom: 'var(--sp-5)' }}>
                            Atlas research data will be preserved.
                        </p>
                        <div style={{ display: 'flex', gap: 'var(--sp-3)', justifyContent: 'flex-end' }}>
                            <button className="btn btn-secondary" onClick={() => setDeleteTarget(null)}>Cancel</button>
                            <button className="btn btn-danger" onClick={() => handleDelete(deleteTarget.name, deleteTarget.vertical)}>
                                <Trash2 size={13} /> Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// ===== ADD VENDOR MODAL =====
function AddVendorModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
    const [form, setForm] = useState({ name: '', vertical: 'database', pricing_url: '', github_repo: '', blog_rss: '' });
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async () => {
        if (!form.name.trim() || !form.pricing_url.trim()) {
            setError('Name and Pricing URL are required.');
            return;
        }
        setSubmitting(true);
        setError('');
        try {
            const res = await fetch(`${API_BASE_URL}/api/vendors`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY },
                body: JSON.stringify({
                    name: form.name.trim(),
                    vertical: form.vertical,
                    pricing_url: form.pricing_url.trim(),
                    github_repo: form.github_repo.trim() || null,
                    blog_rss: form.blog_rss.trim() || null,
                }),
            });
            if (res.ok) {
                onSuccess();
            } else {
                const data = await res.json();
                setError(data.detail || 'Failed to add vendor');
            }
        } catch (e: any) {
            setError(e.message);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" style={{ maxWidth: 500 }} onClick={e => e.stopPropagation()}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-5)' }}>
                    <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--accent-cyan)' }}>+ Add Vendor</h2>
                    <button onClick={onClose} style={{ color: 'var(--text-muted)' }}><X size={18} /></button>
                </div>

                {error && (
                    <div style={{ padding: 'var(--sp-3)', borderRadius: 'var(--radius-sm)', background: 'var(--accent-red-muted)', border: '1px solid var(--accent-red)', color: 'var(--accent-red)', fontSize: 'var(--text-sm)', marginBottom: 'var(--sp-4)' }}>
                        {error}
                    </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)' }}>
                    <div>
                        <label className="input-label">Vendor Name *</label>
                        <input className="input-field" placeholder="e.g. MongoDB, Snowflake" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
                    </div>
                    <div>
                        <label className="input-label">Vertical *</label>
                        <select className="input-field" value={form.vertical} onChange={e => setForm({ ...form, vertical: e.target.value })}>
                            <option value="database">Database</option>
                            <option value="cloud">Cloud</option>
                            <option value="crm">CRM</option>
                        </select>
                    </div>
                    <div>
                        <label className="input-label">Pricing URL *</label>
                        <input className="input-field" placeholder="https://example.com/pricing" value={form.pricing_url} onChange={e => setForm({ ...form, pricing_url: e.target.value })} />
                    </div>
                    <div>
                        <label className="input-label">GitHub Repo</label>
                        <input className="input-field" placeholder="owner/repo" value={form.github_repo} onChange={e => setForm({ ...form, github_repo: e.target.value })} />
                    </div>
                    <div>
                        <label className="input-label">Blog RSS Feed</label>
                        <input className="input-field" placeholder="https://example.com/blog/rss" value={form.blog_rss} onChange={e => setForm({ ...form, blog_rss: e.target.value })} />
                    </div>
                </div>

                <div style={{ display: 'flex', gap: 'var(--sp-3)', justifyContent: 'flex-end', marginTop: 'var(--sp-5)' }}>
                    <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
                    <button className="btn btn-solid" onClick={handleSubmit} disabled={submitting}>
                        {submitting ? 'Adding...' : 'Add Vendor'}
                    </button>
                </div>
            </div>
        </div>
    );
}

// ===== SUB-COMPONENTS =====
function SourceRow({ icon, label, value, isLink }: { icon: React.ReactNode; label: string; value: string | null; isLink?: boolean }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', fontSize: 'var(--text-sm)' }}>
            <span style={{ color: value ? 'var(--accent-green)' : 'var(--text-muted)', display: 'flex' }}>{icon}</span>
            <span style={{ color: 'var(--text-secondary)', minWidth: 72, fontSize: 'var(--text-xs)' }}>{label}</span>
            {value ? (
                isLink ? (
                    <a href={value.startsWith('http') ? value : `https://${value}`} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-cyan)', fontSize: 'var(--text-xs)', opacity: 0.8 }}>
                        {value.length > 42 ? value.substring(0, 42) + '...' : value}
                    </a>
                ) : (
                    <span style={{ color: 'var(--text-primary)', fontSize: 'var(--text-xs)' }}>{value}</span>
                )
            ) : (
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>—</span>
            )}
        </div>
    );
}
