import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Skeleton from '../components/Skeleton';
import { PillFilter } from '../components/design';
import { useSessions, useSessionTrends } from '../hooks/useApi';

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

interface Stats {
    total_verdicts: number;
    this_month: number;
    top_winner: { vendor: string; percentage: number } | null;
    avg_confidence: number;
}

interface TrendItem {
    vendor: string;
    wins: number;
    percentage: number;
}

type ModeKey = 'all' | 'buyer' | 'seller' | 'analyst' | 'sourcing';

const MODE_OPTIONS: { key: ModeKey; label: string }[] = [
    { key: 'all',      label: 'All modes' },
    { key: 'buyer',    label: 'buyer' },
    { key: 'seller',   label: 'seller' },
    { key: 'analyst',  label: 'analyst' },
    { key: 'sourcing', label: 'sourcing' },
];

function shortDate(iso: string | null): string {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function IntelligenceTracker() {
    const navigate = useNavigate();
    const [mode, setMode] = useState<ModeKey>('all');
    const days = 90; // "this quarter" per mock heading

    const backendMode = mode === 'all' ? '' : mode;
    const { data: sessionData, isLoading } = useSessions(days, 20, 0, backendMode, '');
    const { data: trendsData } = useSessionTrends(days, backendMode, '');

    const sessions: Session[] = sessionData?.sessions || [];
    const stats: Stats = sessionData?.stats || {
        total_verdicts: 0, this_month: 0, top_winner: null, avg_confidence: 0,
    };
    const distribution: TrendItem[] = trendsData?.distribution || [];

    const maxPct = Math.max(1, ...distribution.map(d => d.percentage));

    const kpis = [
        { label: 'Total verdicts',       value: String(stats.total_verdicts) },
        { label: 'Sessions this month',  value: String(stats.this_month) },
        { label: 'Avg. confidence',      value: stats.avg_confidence ? `${stats.avg_confidence}%` : '—' },
        { label: 'Verticals covered',    value: '3' },
    ];

    return (
        <div style={{ padding: '36px 44px' }} className="animate-fade-in">
            <h1 style={{
                fontSize: 26, fontWeight: 800, margin: '0 0 4px',
                letterSpacing: '-0.02em',
            }}>Intelligence history</h1>
            <p style={{ fontSize: 14, color: 'var(--text-3)', margin: '0 0 24px' }}>
                Every session, verdict, and trend across verticals.
            </p>

            {/* KPI grid */}
            <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 16, marginBottom: 26,
            }}>
                {isLoading
                    ? Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} style={{
                            background: 'var(--surface-1)', border: '1px solid var(--line)',
                            borderRadius: 14, padding: 18,
                        }}>
                            <Skeleton width={80} height={38} />
                        </div>
                    ))
                    : kpis.map((k, i) => (
                        <div key={i} style={{
                            background: 'var(--surface-1)', border: '1px solid var(--line)',
                            borderRadius: 14, padding: 18,
                        }}>
                            <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 8 }}>{k.label}</div>
                            <div style={{
                                fontFamily: 'var(--font-mono)', fontSize: 24, fontWeight: 700,
                            }}>{k.value}</div>
                        </div>
                    ))
                }
            </div>

            {/* Win distribution */}
            <div style={{
                background: 'var(--surface-1)', border: '1px solid var(--line)',
                borderRadius: 14, padding: 22, marginBottom: 26,
            }}>
                <h2 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 16px' }}>
                    Win distribution — this quarter
                </h2>
                {distribution.length === 0 ? (
                    <div style={{ fontSize: 13, color: 'var(--text-3)', padding: '8px 0' }}>
                        No verdicts yet in this window.
                    </div>
                ) : (
                    distribution.map(d => (
                        <div key={d.vendor} style={{
                            display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10,
                        }}>
                            <span style={{
                                width: 90, fontSize: 12, color: 'var(--text-2)', flexShrink: 0,
                            }}>{d.vendor}</span>
                            <div style={{
                                flex: 1, height: 10, borderRadius: 5,
                                background: 'var(--surface-3)',
                            }}>
                                <div style={{
                                    height: '100%', borderRadius: 5,
                                    width: `${(d.percentage / maxPct) * 100}%`,
                                    background: 'var(--accent)',
                                }} />
                            </div>
                            <span style={{
                                width: 26, fontSize: 12,
                                fontFamily: 'var(--font-mono)', color: 'var(--text-3)',
                                textAlign: 'right',
                            }}>{d.wins}</span>
                        </div>
                    ))
                )}
            </div>

            {/* Mode filter */}
            <div style={{ marginBottom: 16 }}>
                <PillFilter<ModeKey>
                    options={MODE_OPTIONS}
                    value={mode}
                    onChange={setMode}
                />
            </div>

            {/* Session list */}
            {isLoading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} height={62} />
                    ))}
                </div>
            ) : sessions.length === 0 ? (
                <div style={{
                    background: 'var(--surface-1)', border: '1px solid var(--line)',
                    borderRadius: 12, padding: '48px 24px', textAlign: 'center',
                    color: 'var(--text-3)', fontSize: 14,
                }}>
                    No sessions match this filter yet.
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {sessions.map(s => {
                        const clickable = !!s.report_id;
                        return (
                            <div
                                key={s.id}
                                onClick={() => clickable && navigate(`/report/${s.report_id}`)}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 16,
                                    background: 'var(--surface-1)',
                                    border: '1px solid var(--line)',
                                    borderRadius: 12, padding: '14px 18px',
                                    cursor: clickable ? 'pointer' : 'default',
                                }}
                            >
                                <span style={{
                                    fontSize: 11, padding: '4px 10px', borderRadius: 100,
                                    background: 'var(--surface-3)', color: 'var(--text-3)',
                                    fontFamily: 'var(--font-mono)', flexShrink: 0,
                                }}>{s.mode}</span>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{
                                        fontSize: 14, fontWeight: 600,
                                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                    }}>{s.vendors.join(' vs ')}</div>
                                    <div style={{
                                        fontSize: 12, color: 'var(--text-3)', marginTop: 2,
                                    }}>{s.vertical} · {shortDate(s.created_at)}</div>
                                </div>
                                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                                    <div style={{
                                        fontSize: 13, fontWeight: 700,
                                        color: s.winner ? 'var(--success)' : 'var(--text-3)',
                                    }}>{s.winner || '—'}</div>
                                    <div style={{
                                        fontSize: 11, color: 'var(--text-3)',
                                        fontFamily: 'var(--font-mono)',
                                    }}>{s.confidence ? `${s.confidence}% confidence` : '—'}</div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
