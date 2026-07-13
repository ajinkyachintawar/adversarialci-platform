import { useNavigate } from 'react-router-dom';
import Skeleton from '../components/Skeleton';
import { useAllVendors, useSessions } from '../hooks/useApi';

interface EnrichedVendor {
    name: string;
    vertical: string;
    atlas: { research_count: number; status: string } | null;
}

interface Session {
    id: string;
    mode: string;
    vertical: string;
    vendors: string[];
    winner: string | null;
    confidence: number | null;
    created_at: string | null;
    report_id: string | null;
}

const FRESH_ROWS = [
    { label: 'Fresh',                color: 'var(--success)',   key: 'fresh' as const },
    { label: 'Stale',                color: 'var(--warn)',      key: 'stale' as const },
    { label: 'New / never scraped',  color: 'var(--text-3)',    key: 'new' as const },
];

export default function Dashboard() {
    const navigate = useNavigate();
    const { data: vendorData, isLoading: vendorsLoading } = useAllVendors();
    const { data: sessionData, isLoading: sessionsLoading } = useSessions(30, 4, 0);

    const vendors: EnrichedVendor[] = vendorData
        ? [...(vendorData.database || []), ...(vendorData.cloud || []), ...(vendorData.crm || [])]
        : [];
    const sessions: Session[] = sessionData?.sessions || [];
    const stats = sessionData?.stats || { total_verdicts: 0, this_month: 0, top_winner: null, avg_confidence: 0 };

    const totalDocs = vendors.reduce((s, v) => s + (v.atlas?.research_count || 0), 0);
    const freshCounts = {
        fresh: vendors.filter(v => v.atlas?.status === 'fresh').length,
        stale: vendors.filter(v => v.atlas?.status === 'stale').length,
        new:   vendors.filter(v => !v.atlas || v.atlas.status === 'new').length,
    };

    const loading = vendorsLoading || sessionsLoading;

    const kpis = [
        { label: 'Vendors tracked',  value: String(vendors.length),                    trend: '3 verticals',                                    trendColor: 'var(--text-3)' },
        { label: 'Intel documents',  value: String(totalDocs),                         trend: `across ${vendors.length} vendors`,               trendColor: 'var(--text-3)' },
        { label: 'Sessions run',     value: String(stats.total_verdicts),              trend: `${stats.this_month} this month`,                 trendColor: stats.this_month > 0 ? 'var(--success)' : 'var(--text-3)' },
        { label: 'Avg. confidence',  value: stats.avg_confidence ? `${stats.avg_confidence}%` : '—', trend: `across ${stats.total_verdicts} verdicts`, trendColor: 'var(--text-3)' },
    ];

    return (
        <div style={{ padding: '36px 44px' }} className="animate-fade-in">
            {/* Header */}
            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: 28,
            }}>
                <div>
                    <h1 style={{
                        fontSize: 26, fontWeight: 800, margin: '0 0 4px',
                        letterSpacing: '-0.02em',
                    }}>Overview</h1>
                    <p style={{ fontSize: 14, color: 'var(--text-3)', margin: 0 }}>
                        Vendor intelligence &amp; verdict activity across all verticals.
                    </p>
                </div>
                <button
                    onClick={() => navigate('/evaluate')}
                    style={{
                        background: 'var(--accent)', color: 'var(--bg)', border: 'none',
                        padding: '12px 20px', borderRadius: 9,
                        fontFamily: 'inherit', fontSize: 14, fontWeight: 700, cursor: 'pointer',
                    }}
                >
                    + New evaluation
                </button>
            </div>

            {/* KPI grid */}
            <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 16, marginBottom: 32,
            }}>
                {loading
                    ? Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} style={{
                            background: 'var(--surface-1)', border: '1px solid var(--line)',
                            borderRadius: 16, padding: 22,
                        }}>
                            <Skeleton width={100} height={44} />
                        </div>
                    ))
                    : kpis.map((k, i) => (
                        <div key={i} style={{
                            background: 'var(--surface-1)', border: '1px solid var(--line)',
                            borderRadius: 16, padding: 22,
                        }}>
                            <div style={{ fontSize: 13, color: 'var(--text-3)', marginBottom: 10 }}>{k.label}</div>
                            <div style={{
                                fontFamily: 'var(--font-mono)', fontSize: 30, fontWeight: 700,
                                letterSpacing: '-0.02em',
                            }}>{k.value}</div>
                            <div style={{ fontSize: 12, color: k.trendColor, marginTop: 8 }}>{k.trend}</div>
                        </div>
                    ))
                }
            </div>

            {/* Two-column split */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 20 }}>
                {/* Recent verdicts */}
                <div style={{
                    background: 'var(--surface-1)', border: '1px solid var(--line)',
                    borderRadius: 16, padding: 24,
                }}>
                    <div style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        marginBottom: 18,
                    }}>
                        <h2 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>Recent verdicts</h2>
                        <span
                            onClick={() => navigate('/history')}
                            style={{ fontSize: 13, color: 'var(--accent)', cursor: 'pointer' }}
                        >
                            View all →
                        </span>
                    </div>
                    {loading ? (
                        <Skeleton height={160} />
                    ) : sessions.length === 0 ? (
                        <div style={{
                            padding: '32px 0', textAlign: 'center',
                            color: 'var(--text-3)', fontSize: 13,
                        }}>
                            No evaluations yet.{' '}
                            <span
                                onClick={() => navigate('/evaluate')}
                                style={{ color: 'var(--accent)', cursor: 'pointer' }}
                            >
                                Run your first one →
                            </span>
                        </div>
                    ) : (
                        sessions.map(s => {
                            const initial = (s.vendors[0] || '·').slice(0, 2).toUpperCase();
                            return (
                                <div
                                    key={s.id}
                                    onClick={() => s.report_id && navigate(`/report/${s.report_id}`)}
                                    style={{
                                        display: 'flex', alignItems: 'center', gap: 14,
                                        padding: '14px 0', borderTop: '1px solid var(--surface-3)',
                                        cursor: s.report_id ? 'pointer' : 'default',
                                    }}
                                >
                                    <div style={{
                                        width: 34, height: 34, borderRadius: 9,
                                        background: 'var(--surface-2)',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        fontSize: 13, fontWeight: 700, color: 'var(--accent)',
                                        flexShrink: 0,
                                    }}>{initial}</div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{
                                            fontSize: 14, fontWeight: 600,
                                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                        }}>{s.vendors.join(' vs ')}</div>
                                        <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>
                                            {s.mode} · {s.vertical}
                                        </div>
                                    </div>
                                    <div style={{ textAlign: 'right' }}>
                                        <div style={{
                                            fontSize: 13, fontWeight: 700,
                                            color: s.winner ? 'var(--success)' : 'var(--text-3)',
                                        }}>{s.winner || '—'}</div>
                                        <div style={{
                                            fontSize: 11, color: 'var(--text-3)',
                                            marginTop: 2, fontFamily: 'var(--font-mono)',
                                        }}>{s.confidence ? `${s.confidence}%` : '—'}</div>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Top winner + Freshness */}
                <div style={{
                    background: 'var(--surface-1)', border: '1px solid var(--line)',
                    borderRadius: 16, padding: 24,
                }}>
                    <h2 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 18px' }}>Top winner this month</h2>
                    {stats.top_winner ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
                            <div style={{
                                width: 46, height: 46, borderRadius: 12,
                                background: 'var(--success-15)',
                                border: '1px solid var(--success-30)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 700,
                                color: 'var(--success)',
                            }}>01</div>
                            <div>
                                <div style={{ fontSize: 17, fontWeight: 700 }}>{stats.top_winner.vendor}</div>
                                <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                                    Won {stats.top_winner.percentage}% of sessions
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div style={{
                            fontSize: 13, color: 'var(--text-3)', marginBottom: 20,
                            padding: '14px 0',
                        }}>
                            No verdicts yet this month.
                        </div>
                    )}

                    <h2 style={{ fontSize: 15, fontWeight: 700, margin: '20px 0 14px' }}>Freshness</h2>
                    {FRESH_ROWS.map(f => (
                        <div key={f.key} style={{
                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                            padding: '8px 0',
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                                <span style={{
                                    width: 7, height: 7, borderRadius: '50%', background: f.color,
                                }} />
                                {f.label}
                            </div>
                            <span style={{
                                fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-3)',
                            }}>{freshCounts[f.key]}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
