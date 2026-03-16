import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, BarChart3, Target, ShieldAlert, TrendingUp, Radio, Eye, Bell, ArrowRight, RefreshCw, FileText, ChevronDown, Zap, X } from 'lucide-react';
import Skeleton from '../components/Skeleton';
import { useSessions, useSessionTrends } from '../hooks/useApi';


type TabKey = 'history' | 'signals' | 'watchlist';

interface Session {
    id: string;
    mode: string;
    vertical: string;
    vendors: string[];
    winner: string | null;
    confidence: number | null;
    plaintiff_profile: {
        company: string;
        budget: string;
        use_case: string;
        priority: string;
        team_size: string;
    } | null;
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

// ─── Helpers ──────────────────────────────────────────────────

const timeAgo = (iso: string): string => {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days === 1) return 'Yesterday';
    if (days < 30) return `${days}d ago`;
    return d.toLocaleDateString();
};

const modeConfig: Record<string, { icon: typeof Target; label: string; emoji: string; color: string; muted: string; border: string }> = {
    buyer: { icon: Target, label: 'Buyer', emoji: '🛒', color: 'var(--accent-cyan)', muted: 'var(--accent-cyan-muted)', border: 'rgba(0,212,255,0.2)' },
    seller: { icon: ShieldAlert, label: 'Seller', emoji: '🎯', color: 'var(--accent-purple)', muted: 'var(--accent-purple-muted)', border: 'rgba(170,100,255,0.2)' },
    analyst: { icon: BarChart3, label: 'Analyst', emoji: '📊', color: 'var(--accent-green)', muted: 'var(--accent-green-muted)', border: 'rgba(0,255,136,0.2)' },
};

// ─── Component ────────────────────────────────────────────────

export default function IntelligenceTracker() {
    const navigate = useNavigate();
    const [tab, setTab] = useState<TabKey>('history');

    // Filters
    const [filterMode, setFilterMode] = useState('');
    const [filterVertical, setFilterVertical] = useState('');
    const [filterDays, setFilterDays] = useState(30);

    const { data: sessionData, isLoading: loading } = useSessions(filterDays, 20, 0, filterMode, filterVertical);
    const { data: trendsData } = useSessionTrends(filterDays, filterMode, filterVertical);

    const sessions: Session[] = sessionData?.sessions || [];
    const stats: Stats = sessionData?.stats || { total_verdicts: 0, this_month: 0, top_winner: null, avg_confidence: 0 };
    const total: number = sessionData?.total || 0;

    const trends: TrendItem[] = trendsData?.distribution || [];
    const insights: string[] = trendsData?.insights || [];

    // ─── KPI Cards ────────────────────────────────────────────

    const KpiCard = ({ value, label, sub, accent }: { value: string | number; label: string; sub?: string; accent?: string }) => (
        <div className="glass-panel" style={{
            padding: 'var(--sp-5) var(--sp-5)',
            flex: 1,
            minWidth: 0,
        }}>
            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, color: accent || 'var(--text-primary)', fontFamily: 'var(--font-mono)', lineHeight: 1 }}>
                {value}
            </div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', marginTop: 'var(--sp-1)' }}>
                {label}
            </div>
            {sub && (
                <div style={{ fontSize: 'var(--text-xs)', color: accent || 'var(--text-muted)', marginTop: 'var(--sp-1)' }}>
                    {sub}
                </div>
            )}
        </div>
    );

    // ─── Verdict Card ─────────────────────────────────────────

    const VerdictCard = ({ s }: { s: Session }) => {
        const mc = modeConfig[s.mode] || modeConfig.buyer;

        return (
            <div className="glass-panel" style={{
                padding: 'var(--sp-5)',
                marginBottom: 'var(--sp-3)',
                borderColor: mc.border,
                transition: 'border-color 0.2s',
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--sp-3)' }}>
                    <div style={{ display: 'flex', gap: 'var(--sp-3)', alignItems: 'center' }}>
                        {/* Mode badge */}
                        <span style={{
                            fontSize: 'var(--text-xs)', fontWeight: 700,
                            padding: '3px 10px', borderRadius: 'var(--radius-full)',
                            background: mc.muted, color: mc.color,
                            border: `1px solid ${mc.border}`,
                            textTransform: 'uppercase', letterSpacing: '0.05em',
                        }}>
                            {mc.emoji} {mc.label}
                        </span>
                        {/* Vertical badge */}
                        <span style={{
                            fontSize: 'var(--text-xs)',
                            padding: '3px 8px', borderRadius: 'var(--radius-full)',
                            background: 'var(--bg-surface-hover)', color: 'var(--text-muted)',
                            textTransform: 'capitalize',
                        }}>
                            {s.vertical}
                        </span>
                    </div>
                    {/* Timestamp */}
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {s.created_at ? timeAgo(s.created_at) : '—'}
                    </span>
                </div>

                {/* Vendors */}
                <div style={{ fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--sp-2)' }}>
                    {s.vendors.join(' vs ')}
                </div>

                {/* Profile summary */}
                {s.plaintiff_profile && s.plaintiff_profile.company && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginBottom: 'var(--sp-3)' }}>
                        {s.plaintiff_profile.company}
                        {s.plaintiff_profile.budget && ` · ${s.plaintiff_profile.budget}`}
                        {s.plaintiff_profile.priority && ` · ${s.plaintiff_profile.priority} priority`}
                    </div>
                )}
                {s.mode === 'analyst' && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginBottom: 'var(--sp-3)' }}>
                        Full comparison
                    </div>
                )}

                {/* Winner line */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', marginBottom: 'var(--sp-4)' }}>
                    {s.mode === 'buyer' && s.winner && (
                        <>
                            <span style={{ color: 'var(--accent-green)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>
                                🏆 Winner: {s.winner}
                            </span>
                            {s.confidence && (
                                <span style={{
                                    display: 'inline-flex', alignItems: 'center', gap: 'var(--sp-1)',
                                }}>
                                    <span className="progress-bar" style={{ width: 60, height: 4, borderRadius: 2, display: 'inline-block' }}>
                                        <span className="progress-fill" style={{
                                            width: `${s.confidence}%`,
                                            background: s.confidence >= 70 ? 'var(--accent-green)' : 'var(--accent-yellow)',
                                        }} />
                                    </span>
                                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                                        {s.confidence}%
                                    </span>
                                </span>
                            )}
                        </>
                    )}
                    {s.mode === 'seller' && (
                        <span style={{ color: 'var(--accent-purple)', fontSize: 'var(--text-sm)' }}>
                            ⚔️ Battlecard generated
                        </span>
                    )}
                    {s.mode === 'analyst' && (
                        <span style={{ color: 'var(--accent-green)', fontSize: 'var(--text-sm)' }}>
                            📊 Objective comparison (no winner)
                        </span>
                    )}
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
                    <button
                        className="btn btn-secondary"
                        style={{ padding: '0.3rem 0.7rem', fontSize: 'var(--text-xs)' }}
                        onClick={() => {
                            if (s.report_id) navigate(`/report/${s.report_id}`);
                        }}
                        disabled={!s.report_id}
                    >
                        <FileText size={12} />
                        {s.mode === 'buyer' ? 'View Report' : s.mode === 'seller' ? 'View Battlecard' : 'View Comparison'}
                    </button>
                    <button
                        className="btn btn-secondary"
                        style={{ padding: '0.3rem 0.7rem', fontSize: 'var(--text-xs)' }}
                        onClick={() => {
                            const params = new URLSearchParams({ mode: s.mode });
                            navigate(`/evaluate?${params}`);
                        }}
                    >
                        <RefreshCw size={12} /> Re-run
                    </button>
                    <button
                        className="btn btn-secondary"
                        style={{ padding: '0.3rem 0.7rem', fontSize: 'var(--text-xs)', opacity: 0.5 }}
                        disabled
                    >
                        {s.mode === 'seller' ? 'Export PDF' : 'Compare'}
                    </button>
                </div>
            </div>
        );
    };

    // ─── Render ───────────────────────────────────────────────

    return (
        <div className="animate-fade-in">
            {/* Header */}
            <div className="page-header">
                <h1>Intelligence Tracker</h1>
                <p>Monitor competitive signals and track your evaluations.</p>
            </div>

            {/* KPI Cards */}
            <div style={{ display: 'flex', gap: 'var(--sp-4)', marginBottom: 'var(--sp-8)' }}>
                <KpiCard
                    value={stats.total_verdicts}
                    label="Total Verdicts"
                    accent="var(--accent-cyan)"
                />
                <KpiCard
                    value={stats.this_month}
                    label="This Month"
                    accent="var(--accent-green)"
                />
                <KpiCard
                    value={stats.top_winner?.vendor || '—'}
                    label="Top Winner"
                    sub={stats.top_winner ? `(${stats.top_winner.percentage}%)` : undefined}
                    accent="var(--accent-yellow)"
                />
                <KpiCard
                    value={stats.avg_confidence ? `${stats.avg_confidence}%` : '—'}
                    label="Avg Confidence"
                    accent="var(--accent-purple)"
                />
            </div>

            {/* Active filter indicator */}
            {(filterMode || filterVertical || filterDays !== 30) && (
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 'var(--sp-2)',
                    marginBottom: 'var(--sp-6)',
                    fontSize: 'var(--text-xs)', color: 'var(--text-muted)',
                }}>
                    <span style={{ opacity: 0.6 }}>Showing:</span>
                    {filterMode && (
                        <span style={{
                            padding: '2px 8px', borderRadius: 'var(--radius-full)',
                            background: 'rgba(0,212,255,0.08)', color: 'var(--accent-cyan)',
                            border: '1px solid rgba(0,212,255,0.15)',
                        }}>
                            {modeConfig[filterMode]?.emoji} {modeConfig[filterMode]?.label}
                        </span>
                    )}
                    {filterVertical && (
                        <span style={{
                            padding: '2px 8px', borderRadius: 'var(--radius-full)',
                            background: 'rgba(0,255,136,0.08)', color: 'var(--accent-green)',
                            border: '1px solid rgba(0,255,136,0.15)',
                            textTransform: 'capitalize',
                        }}>
                            {filterVertical}
                        </span>
                    )}
                    {filterDays !== 30 && (
                        <span style={{
                            padding: '2px 8px', borderRadius: 'var(--radius-full)',
                            background: 'rgba(255,170,0,0.08)', color: 'var(--accent-yellow)',
                            border: '1px solid rgba(255,170,0,0.15)',
                        }}>
                            {filterDays === 0 ? 'All time' : `Last ${filterDays}d`}
                        </span>
                    )}
                    <button
                        onClick={() => { setFilterMode(''); setFilterVertical(''); setFilterDays(30); }}
                        style={{
                            display: 'inline-flex', alignItems: 'center', gap: '3px',
                            background: 'none', border: 'none', color: 'var(--text-muted)',
                            cursor: 'pointer', fontSize: 'var(--text-xs)', padding: '2px 6px',
                            opacity: 0.7,
                        }}
                    >
                        <X size={11} /> Clear
                    </button>
                </div>
            )}

            {/* Tab Navigation */}
            <div style={{
                display: 'flex', gap: 'var(--sp-1)',
                marginBottom: 'var(--sp-6)',
                padding: 'var(--sp-1)',
                background: 'var(--bg-surface)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border)',
            }}>
                {([
                    { key: 'history' as TabKey, label: 'Verdict History', icon: Clock },
                    { key: 'signals' as TabKey, label: 'Signal Feed', icon: Radio },
                    { key: 'watchlist' as TabKey, label: 'Watchlist', icon: Eye },
                ]).map(t => {
                    const active = tab === t.key;
                    return (
                        <button
                            key={t.key}
                            onClick={() => setTab(t.key)}
                            style={{
                                flex: 1,
                                padding: 'var(--sp-3) var(--sp-4)',
                                borderRadius: 'var(--radius-sm)',
                                border: 'none',
                                background: active ? 'var(--bg-surface-hover)' : 'transparent',
                                color: active ? 'var(--accent-cyan)' : 'var(--text-muted)',
                                fontSize: 'var(--text-sm)',
                                fontWeight: active ? 600 : 400,
                                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--sp-2)',
                                cursor: 'pointer',
                                transition: 'all 0.2s',
                            }}
                        >
                            <t.icon size={15} />
                            {t.label}
                        </button>
                    );
                })}
            </div>

            {/* ═══════════════════════════════════════════════════════
                TAB 1: VERDICT HISTORY
               ═══════════════════════════════════════════════════════ */}
            {tab === 'history' && (
                <div className="animate-fade-in">
                    {/* Filters */}
                    <div style={{
                        display: 'flex', gap: 'var(--sp-3)', marginBottom: 'var(--sp-6)',
                        flexWrap: 'wrap',
                    }}>
                        <div style={{ position: 'relative' }}>
                            <select
                                className="input-field"
                                value={filterMode}
                                onChange={e => setFilterMode(e.target.value)}
                                style={{ paddingRight: 'var(--sp-8)', minWidth: 140, fontSize: 'var(--text-xs)' }}
                            >
                                <option value="">All Modes</option>
                                <option value="buyer">🛒 Buyer</option>
                                <option value="seller">🎯 Seller</option>
                                <option value="analyst">📊 Analyst</option>
                            </select>
                        </div>
                        <div style={{ position: 'relative' }}>
                            <select
                                className="input-field"
                                value={filterVertical}
                                onChange={e => setFilterVertical(e.target.value)}
                                style={{ paddingRight: 'var(--sp-8)', minWidth: 160, fontSize: 'var(--text-xs)' }}
                            >
                                <option value="">All Verticals</option>
                                <option value="database">Database</option>
                                <option value="cloud">Cloud</option>
                                <option value="crm">CRM</option>
                            </select>
                        </div>
                        <div style={{ position: 'relative' }}>
                            <select
                                className="input-field"
                                value={filterDays}
                                onChange={e => setFilterDays(parseInt(e.target.value))}
                                style={{ paddingRight: 'var(--sp-8)', minWidth: 140, fontSize: 'var(--text-xs)' }}
                            >
                                <option value={7}>Last 7 days</option>
                                <option value={30}>Last 30 days</option>
                                <option value={90}>Last 90 days</option>
                                <option value={0}>All time</option>
                            </select>
                        </div>
                    </div>

                    {/* Verdict list */}
                    {loading ? (
                        <div style={{ display: 'grid', gap: 'var(--sp-3)' }}>
                            {[1, 2, 3].map(i => (
                                <Skeleton key={i} height={140} />
                            ))}
                        </div>
                    ) : sessions.length === 0 ? (
                        /* Empty state */
                        <div className="glass-panel" style={{
                            padding: 'var(--sp-12)',
                            textAlign: 'center',
                        }}>
                            <div style={{ fontSize: 48, marginBottom: 'var(--sp-4)' }}>📋</div>
                            <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, marginBottom: 'var(--sp-2)' }}>
                                No evaluations yet
                            </h2>
                            <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginBottom: 'var(--sp-6)', maxWidth: 380, margin: '0 auto var(--sp-6)' }}>
                                Run your first court session to see your verdict history here.
                            </p>
                            <button
                                className="btn btn-primary"
                                onClick={() => navigate('/evaluate')}
                            >
                                Start Evaluation <ArrowRight size={14} />
                            </button>
                        </div>
                    ) : (
                        <>
                            {sessions.map(s => (
                                <VerdictCard key={s.id} s={s} />
                            ))}
                            {sessions.length < total && (
                                <button
                                    className="btn btn-secondary"
                                    style={{ width: '100%', marginTop: 'var(--sp-3)', justifyContent: 'center' }}
                                    onClick={() => {
                                        // Simple load-more by refetching with higher limit
                                        // could be improved with proper pagination
                                    }}
                                >
                                    <ChevronDown size={14} /> Load More ({total - sessions.length} remaining)
                                </button>
                            )}
                        </>
                    )}

                    {/* ─── Verdict Trends ────────────────────────────── */}
                    {trends.length > 0 && (
                        <div className="glass-panel" style={{ padding: 'var(--sp-6)', marginTop: 'var(--sp-8)' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-5)' }}>
                                <TrendingUp size={18} style={{ color: 'var(--accent-cyan)' }} />
                                <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 700 }}>
                                    Winner Distribution
                                </h3>
                                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                                    ({filterVertical || 'all verticals'}, last {filterDays || '∞'} days)
                                </span>
                            </div>

                            <div style={{ display: 'grid', gap: 'var(--sp-3)', marginBottom: 'var(--sp-5)' }}>
                                {trends.map((t, i) => (
                                    <div key={t.vendor} style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
                                        <span style={{
                                            fontSize: 'var(--text-sm)', fontWeight: 600,
                                            color: 'var(--text-primary)',
                                            minWidth: 120, textAlign: 'right',
                                        }}>
                                            {t.vendor}
                                        </span>
                                        <div style={{
                                            flex: 1, height: 20, borderRadius: 'var(--radius-sm)',
                                            background: 'var(--bg-surface-hover)', overflow: 'hidden',
                                        }}>
                                            <div style={{
                                                width: `${t.percentage}%`,
                                                height: '100%',
                                                borderRadius: 'var(--radius-sm)',
                                                background: i === 0 ? 'var(--accent-green)' : i === 1 ? 'var(--accent-cyan)' : 'var(--accent-purple)',
                                                transition: 'width 0.6s ease',
                                            }} />
                                        </div>
                                        <span style={{
                                            fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)',
                                            color: 'var(--text-muted)', minWidth: 60,
                                        }}>
                                            {t.percentage}% ({t.wins})
                                        </span>
                                    </div>
                                ))}
                            </div>

                            {/* Insights */}
                            {insights.length > 0 && (
                                <div style={{
                                    padding: 'var(--sp-3) var(--sp-4)',
                                    background: 'rgba(0,212,255,0.04)',
                                    borderRadius: 'var(--radius-md)',
                                    border: '1px solid rgba(0,212,255,0.1)',
                                }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-2)' }}>
                                        <Zap size={13} style={{ color: 'var(--accent-yellow)' }} />
                                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--accent-yellow)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                            Insights
                                        </span>
                                    </div>
                                    {insights.map((ins, i) => (
                                        <div key={i} style={{
                                            fontSize: 'var(--text-sm)', color: 'var(--text-secondary)',
                                            fontStyle: 'italic', padding: '0.15rem 0',
                                        }}>
                                            "{ins}"
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* ═══════════════════════════════════════════════════════
                TAB 2: SIGNAL FEED (placeholder)
               ═══════════════════════════════════════════════════════ */}
            {tab === 'signals' && (
                <div className="glass-panel animate-fade-in" style={{
                    padding: 'var(--sp-12)',
                    textAlign: 'center',
                }}>
                    <div style={{ fontSize: 56, marginBottom: 'var(--sp-4)' }}>📡</div>
                    <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, marginBottom: 'var(--sp-3)' }}>
                        Signal Feed Coming Soon
                    </h2>
                    <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginBottom: 'var(--sp-6)', maxWidth: 420, margin: '0 auto var(--sp-6)' }}>
                        Track pricing changes, funding rounds, and sentiment shifts across your monitored vendors.
                    </p>
                    <button className="btn btn-secondary" style={{ margin: '0 auto' }}>
                        <Bell size={14} /> Notify Me
                    </button>
                </div>
            )}

            {/* ═══════════════════════════════════════════════════════
                TAB 3: WATCHLIST (placeholder)
               ═══════════════════════════════════════════════════════ */}
            {tab === 'watchlist' && (
                <div className="glass-panel animate-fade-in" style={{
                    padding: 'var(--sp-12)',
                    textAlign: 'center',
                }}>
                    <div style={{ fontSize: 56, marginBottom: 'var(--sp-4)' }}>👁️</div>
                    <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, marginBottom: 'var(--sp-3)' }}>
                        Watchlist Coming Soon
                    </h2>
                    <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginBottom: 'var(--sp-6)', maxWidth: 420, margin: '0 auto var(--sp-6)' }}>
                        Add vendors to your watchlist and get notified when important changes happen.
                    </p>
                    <button className="btn btn-secondary" style={{ margin: '0 auto' }}>
                        <Bell size={14} /> Notify Me
                    </button>
                </div>
            )}
        </div>
    );
}
