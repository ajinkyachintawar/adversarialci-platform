import { useNavigate } from 'react-router-dom';
import { ShoppingCart, Target, BarChart3, ArrowRight } from 'lucide-react';

export default function Dashboard() {
    const navigate = useNavigate();

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

    const coverage = [
        { label: 'Database', count: '9 vendors', color: 'var(--accent-cyan)' },
        { label: 'Cloud', count: '5 vendors', color: 'var(--accent-purple)' },
        { label: 'CRM', count: '4 vendors', color: 'var(--accent-green)' },
    ];

    return (
        <div className="animate-fade-in">
            {/* Hero Section */}
            <div style={{ textAlign: 'center', marginBottom: 'var(--sp-12)', marginTop: 'var(--sp-8)' }}>
                <h1 style={{ fontSize: '3rem', fontWeight: 800, color: 'white', marginBottom: 'var(--sp-2)' }}>
                    AdversarialCI
                </h1>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 500, color: 'var(--accent-cyan)', marginBottom: 'var(--sp-4)' }}>
                    Competitive intelligence through adversarial AI debate.
                </h2>
                <p style={{ 
                    color: 'var(--text-secondary)', 
                    fontSize: '1.1rem', 
                    lineHeight: 1.6, 
                    maxWidth: 600, 
                    margin: '0 auto' 
                }}>
                    AI advocates argue for each vendor. A judge weighs evidence and delivers a verdict. 
                    Get data-backed recommendations in minutes — not weeks of analyst research.
                </p>
            </div>

            {/* How It Works Section */}
            <div style={{ marginBottom: 'var(--sp-12)' }}>
                <div className="section-title" style={{ marginBottom: 'var(--sp-6)', textAlign: 'center' }}>How It Works</div>
                <div className="glass-panel" style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(4, 1fr)', 
                    gap: 'var(--sp-6)', 
                    padding: 'var(--sp-8)' 
                }}>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '2rem', marginBottom: 'var(--sp-3)' }}>🎯</div>
                        <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--sp-2)' }}>Define Mission</h3>
                        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', lineHeight: 1.5 }}>
                            Budget, scale, use case
                        </p>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '2rem', marginBottom: 'var(--sp-3)' }}>⚔️</div>
                        <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--sp-2)' }}>AI Advocates Debate</h3>
                        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', lineHeight: 1.5 }}>
                            3 rounds of arguments
                        </p>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '2rem', marginBottom: 'var(--sp-3)' }}>⚖️</div>
                        <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--sp-2)' }}>Judge Evaluates</h3>
                        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', lineHeight: 1.5 }}>
                            Scores across 7 dimensions
                        </p>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '2rem', marginBottom: 'var(--sp-3)' }}>📊</div>
                        <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--sp-2)' }}>Get Verdict</h3>
                        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', lineHeight: 1.5 }}>
                            Actionable recommendation
                        </p>
                    </div>
                </div>
            </div>

            {/* Launch Mission Section */}
            <div style={{ marginBottom: 'var(--sp-12)' }}>
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

            {/* Coverage Section */}
            <div style={{ marginBottom: 'var(--sp-8)' }}>
                <div className="section-title" style={{ marginBottom: 'var(--sp-4)' }}>Coverage</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--sp-4)' }}>
                    {coverage.map((c) => (
                        <div key={c.label} className="glass-panel" style={{ padding: 'var(--sp-4)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{c.label}</span>
                            <span style={{ color: c.color, fontWeight: 500 }}>{c.count}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}