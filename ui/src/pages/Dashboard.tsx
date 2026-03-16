import { useNavigate } from 'react-router-dom';
import { Database, FileText, CheckCircle2, AlertTriangle, ShoppingCart, Target, BarChart3, ArrowRight, Activity } from 'lucide-react';
import Skeleton from '../components/Skeleton';
import ErrorState from '../components/ErrorState';
import { useAllVendors } from '../hooks/useApi';

interface EnrichedVendor {
    name: string;
    vertical: string;
    atlas: { research_count: number; status: string; last_scraped: string | null } | null;
}

export default function Dashboard() {
    const navigate = useNavigate();
    const { data, isLoading, error, refetch } = useAllVendors();

    const vendors: EnrichedVendor[] = data
        ? [...(data.database || []), ...(data.cloud || []), ...(data.crm || [])]
        : [];

    const totalVendors = vendors.length;
    const totalResearch = vendors.reduce((sum, v) => sum + (v.atlas?.research_count || 0), 0);
    const freshCount = vendors.filter(v => v.atlas?.status === 'fresh').length;
    const staleCount = vendors.filter(v => v.atlas?.status === 'stale' || v.atlas?.status === 'new').length;

    const verticals = [
        { key: 'database', label: 'Database', color: 'var(--accent-cyan)' },
        { key: 'cloud', label: 'Cloud', color: 'var(--accent-purple)' },
        { key: 'crm', label: 'CRM', color: 'var(--accent-green)' },
    ];

    const getVerticalStats = (vKey: string) => {
        const vVendors = vendors.filter(v => v.vertical === vKey);
        const fresh = vVendors.filter(v => v.atlas?.status === 'fresh').length;
        return { total: vVendors.length, fresh, pct: vVendors.length > 0 ? Math.round((fresh / vVendors.length) * 100) : 0 };
    };

    const modes = [
        {
            key: 'buyer',
            icon: ShoppingCart,
            title: 'Buyer Evaluation',
            desc: 'Compare vendors against your specific requirements, budget, and use case. Get a data-backed recommendation.',
            color: 'var(--accent-cyan)',
            mutedColor: 'var(--accent-cyan-muted)',
        },
        {
            key: 'seller',
            icon: Target,
            title: 'Seller Battlecard',
            desc: 'Generate competitive positioning and talking points against rival products for your sales team.',
            color: 'var(--accent-purple)',
            mutedColor: 'var(--accent-purple-muted)',
        },
        {
            key: 'analyst',
            icon: BarChart3,
            title: 'Analyst Comparison',
            desc: 'Objective, data-driven market analysis across all evaluation dimensions without buyer bias.',
            color: 'var(--accent-green)',
            mutedColor: 'var(--accent-green-muted)',
        },
    ];

    if (error) {
        return (
            <div className="animate-fade-in">
                <div className="page-header"><h1>Command Center</h1><p>Overview of all intelligence operations.</p></div>
                <ErrorState message="Failed to connect to backend. Is the server running?" onRetry={() => refetch()} />
            </div>
        );
    }

    return (
        <div className="animate-fade-in">
            <div className="page-header">
                <h1>Command Center</h1>
                <p>Overview of all intelligence operations and vendor profiles.</p>
            </div>

            {/* KPI Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--sp-4)', marginBottom: 'var(--sp-8)' }}>
                {isLoading ? (
                    Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} className="glass-panel kpi-card"><Skeleton width={120} height={44} /></div>
                    ))
                ) : (
                    [
                        { label: 'Total Vendors', value: totalVendors, icon: <Database size={18} />, color: 'var(--accent-cyan)', bg: 'var(--accent-cyan-muted)' },
                        { label: 'Intel Documents', value: totalResearch, icon: <FileText size={18} />, color: 'var(--accent-purple)', bg: 'var(--accent-purple-muted)' },
                        { label: 'Fresh Data', value: freshCount, icon: <CheckCircle2 size={18} />, color: 'var(--accent-green)', bg: 'var(--accent-green-muted)' },
                        { label: 'Needs Refresh', value: staleCount, icon: <AlertTriangle size={18} />, color: 'var(--accent-yellow)', bg: 'var(--accent-yellow-muted)' },
                    ].map((stat, i) => (
                        <div key={i} className="glass-panel kpi-card">
                            <div className="kpi-icon" style={{ background: stat.bg, color: stat.color }}>{stat.icon}</div>
                            <div>
                                <div className="kpi-value" style={{ color: stat.color }}>{stat.value}</div>
                                <div className="kpi-label">{stat.label}</div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Mode Cards */}
            <div style={{ marginBottom: 'var(--sp-8)' }}>
                <div className="section-title" style={{ marginBottom: 'var(--sp-4)' }}>Launch Mission</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--sp-4)' }}>
                    {modes.map((m) => (
                        <div
                            key={m.key}
                            className="glass-panel"
                            style={{
                                padding: 'var(--sp-6)',
                                cursor: 'pointer',
                                transition: 'all 0.25s ease',
                                position: 'relative',
                                overflow: 'hidden',
                            }}
                            onClick={() => navigate(`/evaluate?mode=${m.key}`)}
                            onMouseEnter={e => {
                                (e.currentTarget as HTMLElement).style.borderColor = m.color;
                                (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)';
                            }}
                            onMouseLeave={e => {
                                (e.currentTarget as HTMLElement).style.borderColor = '';
                                (e.currentTarget as HTMLElement).style.transform = '';
                            }}
                        >
                            <div style={{
                                display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', marginBottom: 'var(--sp-3)',
                            }}>
                                <div style={{
                                    width: 36, height: 36, borderRadius: 'var(--radius-md)',
                                    background: m.mutedColor, display: 'flex', alignItems: 'center',
                                    justifyContent: 'center', color: m.color,
                                }}>
                                    <m.icon size={18} />
                                </div>
                                <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 600, color: m.color }}>{m.title}</h3>
                            </div>
                            <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', lineHeight: 1.6, marginBottom: 'var(--sp-5)' }}>
                                {m.desc}
                            </p>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', color: m.color, fontSize: 'var(--text-sm)', fontWeight: 500 }}>
                                Launch <ArrowRight size={14} />
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Data Health */}
            <div style={{ marginBottom: 'var(--sp-8)' }}>
                <div className="section-title" style={{ marginBottom: 'var(--sp-4)' }}>
                    <Activity size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 'var(--sp-2)' }} />
                    Data Health
                </div>
                <div className="glass-panel" style={{ padding: 'var(--sp-6)' }}>
                    {isLoading ? (
                        <Skeleton count={3} height={32} />
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-5)' }}>
                            {verticals.map(v => {
                                const stats = getVerticalStats(v.key);
                                return (
                                    <div key={v.key} style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-4)' }}>
                                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', minWidth: 80, fontWeight: 500 }}>{v.label}</span>
                                        <div style={{ flex: 1 }}>
                                            <div className="progress-bar" style={{ height: 6, borderRadius: 3 }}>
                                                <div
                                                    className="progress-fill"
                                                    style={{
                                                        width: `${stats.pct}%`,
                                                        background: stats.pct >= 70 ? 'var(--accent-green)' : stats.pct >= 40 ? 'var(--accent-yellow)' : 'var(--accent-red)',
                                                    }}
                                                />
                                            </div>
                                        </div>
                                        <span style={{
                                            fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)',
                                            color: stats.pct >= 70 ? 'var(--accent-green)' : stats.pct >= 40 ? 'var(--accent-yellow)' : 'var(--text-muted)',
                                            minWidth: 50, textAlign: 'right',
                                        }}>
                                            {stats.pct}%
                                        </span>
                                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', minWidth: 80 }}>
                                            {stats.fresh}/{stats.total} fresh
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}