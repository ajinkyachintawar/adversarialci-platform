import { useNavigate } from 'react-router-dom';
import { ShoppingCart, Target, BarChart3, ArrowRight } from 'lucide-react';

export default function Dashboard() {
    const navigate = useNavigate();

    const modes = [
        {
            key: 'buyer',
            icon: ShoppingCart,
            title: 'Buyer Evaluation',
            question: '"Which vendor fits my stack?"',
            outcomes: ['Recommendation', 'tradeoffs', 'questions to ask'],
            color: 'var(--accent-cyan)',
            mutedColor: 'var(--accent-cyan-muted)',
        },
        {
            key: 'seller',
            icon: Target,
            title: 'Seller Battlecard',
            question: '"How do I beat Competitor X?"',
            outcomes: ['Battlecard', 'attack points', 'objection handlers'],
            color: 'var(--accent-purple)',
            mutedColor: 'var(--accent-purple-muted)',
        },
        {
            key: 'analyst',
            icon: BarChart3,
            title: 'Analyst Comparison',
            question: '"Compare these objectively"',
            outcomes: ['Scorecard', '7 dimensions', 'no bias'],
            color: 'var(--accent-green)',
            mutedColor: 'var(--accent-green-muted)',
        },
    ];

    return (
        <div className="animate-fade-in">
            {/* Hero Section */}
            <div style={{ textAlign: 'center', marginBottom: 'var(--sp-12)', marginTop: 'var(--sp-8)' }}>
                <h1 style={{ fontSize: '3rem', fontWeight: 800, color: 'white', marginBottom: 'var(--sp-2)' }}>
                    AdversarialCI
                </h1>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 500, color: 'var(--accent-cyan)', marginBottom: 'var(--sp-4)' }}>
                    Let AI lawyers fight it out. You get the verdict.
                </h2>
                <p style={{
                    color: 'var(--text-secondary)',
                    fontSize: '1.1rem',
                    lineHeight: 1.6,
                    maxWidth: 600,
                    margin: '0 auto'
                }}>
                    Pick vendors to compare. AI advocates argue each side across 3 rounds. A judge scores 7 dimensions and delivers a verdict — with reasoning, tradeoffs, and next steps.
                </p>
            </div>

            {/* Mode Cards */}
            <div style={{ marginBottom: 'var(--sp-12)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--sp-6)' }}>
                    {modes.map((m) => (
                        <div
                            key={m.key}
                            className="glass-panel"
                            style={{
                                padding: 'var(--sp-8)',
                                display: 'flex',
                                flexDirection: 'column',
                                position: 'relative',
                                overflow: 'hidden',
                                borderTop: `4px solid ${m.color}`,
                            }}
                        >
                            <div style={{
                                display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', marginBottom: 'var(--sp-4)',
                            }}>
                                <div style={{
                                    width: 40, height: 40, borderRadius: 'var(--radius-md)',
                                    background: m.mutedColor, display: 'flex', alignItems: 'center',
                                    justifyContent: 'center', color: m.color,
                                }}>
                                    <m.icon size={20} />
                                </div>
                                <h3 style={{ fontSize: '1.2rem', fontWeight: 600, color: m.color }}>{m.title}</h3>
                            </div>

                            <p style={{
                                color: 'var(--text-muted)',
                                fontStyle: 'italic',
                                fontSize: '1.05rem',
                                marginBottom: 'var(--sp-6)',
                                borderLeft: `2px solid ${m.mutedColor}`,
                                paddingLeft: 'var(--sp-3)'
                            }}>
                                {m.question}
                            </p>

                            <ul style={{
                                listStyle: 'none',
                                padding: 0,
                                margin: '0 0 var(--sp-8) 0',
                                flex: 1
                            }}>
                                {m.outcomes.map((outcome, i) => (
                                    <li key={i} style={{
                                        color: 'var(--text-secondary)',
                                        marginBottom: 'var(--sp-3)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 'var(--sp-3)'
                                    }}>
                                        <span style={{ color: m.color, fontSize: '0.8rem' }}>•</span>
                                        {i === 0 ? outcome : `+ ${outcome}`}
                                    </li>
                                ))}
                            </ul>

                            <button
                                onClick={() => navigate(`/evaluate?mode=${m.key}`)}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: 'var(--sp-2)',
                                    background: m.mutedColor,
                                    color: m.color,
                                    border: 'none',
                                    padding: 'var(--sp-3)',
                                    borderRadius: 'var(--radius-md)',
                                    fontSize: 'var(--text-sm)',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                    transition: 'all 0.2s ease',
                                    width: '100%'
                                }}
                                onMouseEnter={e => {
                                    (e.currentTarget as HTMLElement).style.background = m.color;
                                    (e.currentTarget as HTMLElement).style.color = '#fff';
                                }}
                                onMouseLeave={e => {
                                    (e.currentTarget as HTMLElement).style.background = m.mutedColor;
                                    (e.currentTarget as HTMLElement).style.color = m.color;
                                }}
                            >
                                Launch <ArrowRight size={16} />
                            </button>
                        </div>
                    ))}
                </div>
            </div>

            {/* Footer / Tech Stack */}
            <div style={{ textAlign: 'center', paddingBottom: 'var(--sp-12)' }}>
                <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginBottom: 'var(--sp-2)' }}>
                    18 vendors across Database • Cloud • CRM
                </p>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', opacity: 0.5 }}>
                    Built with: LangGraph • Groq • FastAPI • React • MongoDB
                </p>
            </div>
        </div>
    );
}