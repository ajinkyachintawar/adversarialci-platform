import { useNavigate } from 'react-router-dom';
import { TopBar } from '../components/design';
import { useAllVendors, useSessions } from '../hooks/useApi';

interface EnrichedVendor { atlas: { research_count: number } | null; }

const FEATURES = [
    { icon: '◆', bg: 'var(--accent-12)',       title: 'Adversarial argument',      body: 'Vendors get argued for and against by dedicated AI counsel before a judge renders a verdict.' },
    { icon: '◈', bg: 'var(--success-12)',      title: 'Evidence-backed research',  body: 'Pricing pages, GitHub activity, blog posts, HN threads, and migration complaints — all scraped and cited.' },
    { icon: '▤', bg: 'oklch(0.7 0.09 75 / 0.12)', title: 'Config-driven verticals',   body: 'Databases, cloud, CRM today — each vertical defines its own intake questions and scoring dimensions.' },
];

export default function Landing() {
    const navigate = useNavigate();
    const { data: vendorData } = useAllVendors();
    const { data: sessionData } = useSessions(30, 1, 0);

    const vendors: EnrichedVendor[] = vendorData
        ? [...(vendorData.database || []), ...(vendorData.cloud || []), ...(vendorData.crm || [])]
        : [];
    const totalDocs = vendors.reduce((sum, v) => sum + (v.atlas?.research_count || 0), 0);

    const stats = [
        { value: '3',                                       label: 'Verticals covered' },
        { value: String(vendors.length || 0),               label: 'Vendors tracked' },
        { value: String(totalDocs),                         label: 'Intel documents' },
        { value: String(sessionData?.stats?.total_verdicts ?? 0), label: 'Verdicts delivered' },
    ];

    return (
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>
            <TopBar variant="landing" />

            <main style={{
                maxWidth: 1280, margin: '0 auto', padding: '80px 48px 60px',
                width: '100%', boxSizing: 'border-box',
            }}>
                <div style={{ maxWidth: 760 }}>
                    <div style={{
                        display: 'inline-flex', alignItems: 'center', gap: 8,
                        padding: '6px 12px', borderRadius: 100,
                        background: 'var(--accent-10)',
                        border: '1px solid var(--accent-25)',
                        marginBottom: 28,
                    }}>
                        <span style={{
                            width: 6, height: 6, borderRadius: '50%',
                            background: 'var(--success)',
                            animation: 'acp-pulse 2s ease-in-out infinite',
                        }} />
                        <span style={{
                            fontFamily: 'var(--font-mono)', fontSize: 12,
                            color: 'var(--accent)', letterSpacing: '0.02em',
                        }}>
                            Multi-stage AI evaluation pipeline
                        </span>
                    </div>

                    <h1 style={{
                        fontFamily: 'var(--font-serif)',
                        fontSize: 58, lineHeight: 1.08, fontWeight: 500,
                        letterSpacing: '-0.01em', margin: '0 0 24px',
                    }}>
                        Vendor decisions,<br />argued to a verdict.
                    </h1>

                    <p style={{
                        fontSize: 19, lineHeight: 1.6, color: 'var(--text-3)',
                        margin: '0 0 40px', maxWidth: 600,
                    }}>
                        AdversarialCI runs your vendor shortlist through adversarial research, argument,
                        and judgment — and hands back a report with a winner, evidence, and the tradeoffs
                        you'd actually ask a colleague about.
                    </p>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                        <button
                            onClick={() => navigate('/login')}
                            style={{
                                background: 'var(--accent)', color: 'var(--bg)', border: 'none',
                                padding: '14px 26px', borderRadius: 10, fontFamily: 'inherit',
                                fontSize: 15, fontWeight: 700, cursor: 'pointer',
                                display: 'flex', alignItems: 'center', gap: 8,
                            }}
                        >
                            Start an evaluation →
                        </button>
                        <button
                            onClick={() => navigate('/vendors')}
                            style={{
                                background: 'none', border: 'none', color: 'var(--text)',
                                padding: '14px 10px', fontFamily: 'inherit',
                                fontSize: 15, fontWeight: 600, cursor: 'pointer',
                            }}
                        >
                            Browse vendor intel →
                        </button>
                    </div>
                </div>

                <div id="landing-features" style={{
                    display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: 20, marginTop: 90, scrollMarginTop: 100,
                }}>
                    {FEATURES.map((f, i) => (
                        <div key={i} style={{
                            background: 'var(--surface-1)',
                            border: '1px solid var(--line)',
                            borderRadius: 16, padding: 28,
                        }}>
                            <div style={{
                                width: 40, height: 40, borderRadius: 10, background: f.bg,
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                marginBottom: 20, fontSize: 18,
                            }}>{f.icon}</div>
                            <h3 style={{
                                fontSize: 17, fontWeight: 700, margin: '0 0 8px',
                                letterSpacing: '-0.01em',
                            }}>{f.title}</h3>
                            <p style={{
                                fontSize: 14, lineHeight: 1.6, color: 'var(--text-3)', margin: 0,
                            }}>{f.body}</p>
                        </div>
                    ))}
                </div>

                <div id="landing-stats" style={{
                    marginTop: 90, background: 'var(--surface-1)',
                    border: '1px solid var(--line)', borderRadius: 20, padding: 40,
                    display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 32,
                    scrollMarginTop: 100,
                }}>
                    {stats.map((s, i) => (
                        <div key={i}>
                            <div style={{
                                fontFamily: 'var(--font-mono)', fontSize: 32, fontWeight: 700,
                                color: 'var(--accent)', letterSpacing: '-0.02em',
                            }}>{s.value}</div>
                            <div style={{ fontSize: 13, color: 'var(--text-3)', marginTop: 6 }}>{s.label}</div>
                        </div>
                    ))}
                </div>
            </main>

            <footer style={{
                marginTop: 'auto', borderTop: '1px solid var(--line)',
                padding: '24px 48px', maxWidth: 1280,
                marginLeft: 'auto', marginRight: 'auto', width: '100%',
                boxSizing: 'border-box',
                display: 'flex', justifyContent: 'space-between',
                color: 'var(--text-3)', fontSize: 13,
            }}>
                <span>© 2026 AdversarialCI</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>status: operational</span>
            </footer>
        </div>
    );
}
