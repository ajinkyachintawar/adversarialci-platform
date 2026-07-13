import { useNavigate } from 'react-router-dom';
import { TopBar } from '../components/design';
import { useAllVendors } from '../hooks/useApi';

interface EnrichedVendor { vertical: string; }

const PIPELINE_STAGES = [
    { n: '1', title: 'Research', body: 'Pricing pages, GitHub activity, blog posts, HN threads, and migration/complaint queries are scraped per vendor and indexed as evidence.' },
    { n: '2', title: 'Argue',    body: 'Each vendor gets dedicated AI counsel that builds the strongest case for it — and a rebuttal against the others — grounded in the research.' },
    { n: '3', title: 'Judge',    body: 'An impartial judge weighs the arguments against your stated priorities across the scoring dimensions for that vertical.' },
    { n: '4', title: 'Report',   body: 'A structured verdict comes back: winner, confidence, per-vendor scorecards, tradeoffs, and next steps — in one shareable report.' },
];

const MODES = [
    { label: 'Buyer',    body: '"Which vendor should I pick?" — the primary flow. Compare 2-4 vendors against your profile and get a declared winner.' },
    { label: 'Seller',   body: '"How do I position against a competitor?" — pick your company and 1-3 rivals to see where you win and lose.' },
    { label: 'Analyst',  body: 'A neutral side-by-side comparison with no declared winner — just the evidence and scores.' },
    { label: 'Sourcing', body: 'A research/freshness pass only — re-index vendor intel without running a full court session.' },
];

const VERTICALS: { key: 'database' | 'cloud' | 'crm'; icon: string; label: string }[] = [
    { key: 'database', icon: '▤', label: 'Database' },
    { key: 'cloud',    icon: '◇', label: 'Cloud' },
    { key: 'crm',      icon: '◈', label: 'CRM' },
];

export default function About() {
    const navigate = useNavigate();
    const { data: vendorData } = useAllVendors();

    const counts = {
        database: (vendorData?.database as EnrichedVendor[] | undefined)?.length ?? 0,
        cloud:    (vendorData?.cloud    as EnrichedVendor[] | undefined)?.length ?? 0,
        crm:      (vendorData?.crm      as EnrichedVendor[] | undefined)?.length ?? 0,
    };

    return (
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>
            <TopBar variant="about" />

            <main style={{
                maxWidth: 900, margin: '0 auto', padding: '60px 48px 100px',
                width: '100%', boxSizing: 'border-box',
            }}>
                <div style={{
                    display: 'inline-flex', alignItems: 'center', gap: 8,
                    padding: '6px 12px', borderRadius: 100,
                    background: 'var(--accent-10)',
                    border: '1px solid var(--accent-25)',
                    marginBottom: 24,
                }}>
                    <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 12,
                        color: 'var(--accent)', letterSpacing: '0.02em',
                    }}>About</span>
                </div>

                <h1 style={{
                    fontFamily: 'var(--font-serif)',
                    fontSize: 44, lineHeight: 1.15, fontWeight: 500,
                    letterSpacing: '-0.01em', margin: '0 0 20px',
                }}>
                    What AdversarialCI actually does
                </h1>

                <p style={{
                    fontSize: 17, lineHeight: 1.7, color: 'var(--text-2)',
                    margin: '0 0 48px', maxWidth: 700,
                }}>
                    Most vendor comparisons are marketing copy with a checkmark grid. AdversarialCI runs
                    your shortlist through a real pipeline — research pulled from primary sources,
                    arguments made and stress-tested, a verdict rendered — so the recommendation has
                    evidence behind it, not vibes.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 56 }}>
                    {PIPELINE_STAGES.map(ps => (
                        <div key={ps.n} style={{
                            display: 'flex', alignItems: 'flex-start', gap: 18,
                            background: 'var(--surface-1)',
                            border: '1px solid var(--line)',
                            borderRadius: 14, padding: '20px 24px',
                        }}>
                            <div style={{
                                width: 34, height: 34, borderRadius: 9,
                                background: 'var(--accent-12)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontFamily: 'var(--font-mono)', fontWeight: 700,
                                color: 'var(--accent)', flexShrink: 0,
                            }}>{ps.n}</div>
                            <div>
                                <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>{ps.title}</div>
                                <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-3)' }}>{ps.body}</div>
                            </div>
                        </div>
                    ))}
                </div>

                <h2 style={{ fontSize: 22, fontWeight: 800, margin: '0 0 20px', letterSpacing: '-0.01em' }}>
                    Four ways to run it
                </h2>
                <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: 14, marginBottom: 56,
                }}>
                    {MODES.map(m => (
                        <div key={m.label} style={{
                            background: 'var(--surface-1)',
                            border: '1px solid var(--line)',
                            borderRadius: 14, padding: 20,
                        }}>
                            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6, color: 'var(--accent)' }}>
                                {m.label}
                            </div>
                            <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-2)' }}>{m.body}</div>
                        </div>
                    ))}
                </div>

                <h2 style={{ fontSize: 22, fontWeight: 800, margin: '0 0 20px', letterSpacing: '-0.01em' }}>
                    Built to grow past three verticals
                </h2>
                <p style={{
                    fontSize: 14, lineHeight: 1.7, color: 'var(--text-3)',
                    margin: '0 0 20px', maxWidth: 700,
                }}>
                    Databases, cloud, and CRM ship today. Every vertical is config, not code — its own
                    intake questions and its own scoring dimensions — so adding the next one doesn't
                    touch the UI.
                </p>
                <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: 14, marginBottom: 56,
                }}>
                    {VERTICALS.map(v => (
                        <div key={v.key} style={{
                            background: 'var(--surface-1)',
                            border: '1px solid var(--line)',
                            borderRadius: 14, padding: 18, textAlign: 'center',
                        }}>
                            <div style={{ fontSize: 20, marginBottom: 8 }}>{v.icon}</div>
                            <div style={{ fontSize: 14, fontWeight: 700 }}>{v.label}</div>
                            <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>
                                {counts[v.key]} vendors tracked
                            </div>
                        </div>
                    ))}
                </div>

                <div style={{
                    background: 'var(--surface-1)',
                    border: '1px solid var(--line)',
                    borderRadius: 18, padding: 32,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                }}>
                    <div>
                        <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>
                            Ready to see a verdict?
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--text-3)' }}>
                            Sign in and run your first evaluation in minutes.
                        </div>
                    </div>
                    <button
                        onClick={() => navigate('/login')}
                        style={{
                            background: 'var(--accent)', color: 'var(--bg)', border: 'none',
                            padding: '13px 24px', borderRadius: 9, fontFamily: 'inherit',
                            fontSize: 14, fontWeight: 700, cursor: 'pointer', flexShrink: 0,
                        }}
                    >
                        Start an evaluation →
                    </button>
                </div>
            </main>
        </div>
    );
}
