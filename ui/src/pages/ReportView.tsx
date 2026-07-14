import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Copy, Download } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useReport } from '../hooks/useApi';
import {
    parseReport,
    extractWinner,
    extractConfidence,
    extractSummary,
    extractProfile,
    extractScorecard,
    extractTradeoffs,
    extractAnalystSummary,
    extractDataQuality,
    extractAnalystMatrix,
    extractDimensionAnalysis,
    extractVendorProfiles,
    extractBestFitScenarios,
    extractDimensionBreakdown,
    extractRunnerUp,
    extractQuestions,
    extractBuyerNextSteps,
    extractConfidenceBreakdown,
} from '../lib/reportParser';

export default function ReportView() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [copied, setCopied] = useState(false);

    const { data, isLoading, error: queryError } = useReport(id);
    const content: string = data?.content || data?.verdict || '';
    const parsed = content ? parseReport(content) : null;

    const winner     = content ? extractWinner(content)     : '';
    const confidence = content ? extractConfidence(content) : 0;
    const summary    = content ? extractSummary(content)    : '';
    const profile    = content ? extractProfile(content)    : null;
    const scorecard  = content ? extractScorecard(content)  : null;
    const tradeoffs  = content ? extractTradeoffs(content)  : null;

    const mode = parsed?.mode || 'buyer';
    const hasWinner = !!winner && mode !== 'analyst';
    const isAnalyst = mode === 'analyst';
    const isBuyer   = mode === 'buyer';
    const analystSummary  = content && isAnalyst ? extractAnalystSummary(content)   : null;
    const dataQuality     = content && isAnalyst ? extractDataQuality(content)      : null;
    const analystMatrix   = content && isAnalyst ? extractAnalystMatrix(content)    : null;
    const dimAnalysis     = content && isAnalyst ? extractDimensionAnalysis(content): [];
    const vendorProfiles  = content && isAnalyst ? extractVendorProfiles(content)   : [];
    const bestFit         = content && isAnalyst ? extractBestFitScenarios(content) : [];
    const dimBreakdown    = content && isBuyer   ? extractDimensionBreakdown(content)   : [];
    const runnerUp        = content && isBuyer   ? extractRunnerUp(content)             : null;
    const questions       = content && isBuyer   ? extractQuestions(content)            : [];
    const nextSteps       = content && isBuyer   ? extractBuyerNextSteps(content)       : [];
    const confBreakdown   = content && isBuyer   ? extractConfidenceBreakdown(content)  : null;

    const handleCopy = () => {
        navigator.clipboard.writeText(content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };
    const handleDownload = () => {
        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${id}.md`;
        a.click();
        URL.revokeObjectURL(url);
    };

    if (isLoading) {
        return (
            <div style={{ padding: '36px 44px', color: 'var(--text-3)', fontSize: 14 }}>
                Loading report…
            </div>
        );
    }
    if (queryError) {
        return (
            <div style={{ padding: '36px 44px', color: 'var(--danger)', fontSize: 14 }}>
                Error: {(queryError as Error).message}
            </div>
        );
    }
    if (!content) {
        return (
            <div style={{ padding: '36px 44px', color: 'var(--text-3)', fontSize: 14 }}>
                Report not found.
            </div>
        );
    }

    const profilePills = buildProfilePills(profile, mode, scorecard?.vendors.length);

    return (
        <div style={{ padding: '36px 44px', maxWidth: 980 }} className="animate-fade-in">
            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: 6,
            }}>
                <span
                    onClick={() => navigate('/history')}
                    style={{ fontSize: 13, color: 'var(--text-3)', cursor: 'pointer' }}
                >← Back to history</span>
                <span style={{
                    fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-3)',
                }}>{mode} · {parsed?.generatedAt || ''}</span>
            </div>

            <div style={{
                display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
                gap: 12, margin: '14px 0 24px',
            }}>
                <h1 style={{
                    fontSize: 26, fontWeight: 800, letterSpacing: '-0.02em', margin: 0,
                }}>{parsed?.title || 'Vendor evaluation'}</h1>
                <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                    <button
                        onClick={handleCopy}
                        style={{
                            display: 'flex', alignItems: 'center', gap: 6,
                            padding: '8px 14px', background: 'var(--surface-3)',
                            border: '1px solid var(--line-2)', borderRadius: 8,
                            color: 'var(--text)', fontFamily: 'inherit', fontSize: 12, fontWeight: 600,
                            cursor: 'pointer',
                        }}
                    ><Copy size={13} /> {copied ? 'Copied!' : 'Copy'}</button>
                    <button
                        onClick={handleDownload}
                        style={{
                            display: 'flex', alignItems: 'center', gap: 6,
                            padding: '8px 14px', background: 'var(--accent)',
                            border: 'none', borderRadius: 8, color: 'var(--bg)',
                            fontFamily: 'inherit', fontSize: 12, fontWeight: 700,
                            cursor: 'pointer',
                        }}
                    ><Download size={13} /> Download</button>
                </div>
            </div>

            {profilePills.length > 0 && (
                <div style={{
                    display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 24,
                }}>
                    {profilePills.map((p, i) => (
                        <span key={i} style={{
                            fontSize: 12, padding: '6px 12px', borderRadius: 100,
                            background: 'var(--surface-2)', border: '1px solid var(--line-2)',
                            color: 'var(--text-2)',
                        }}>{p}</span>
                    ))}
                </div>
            )}

            {hasWinner ? (
                <WinnerCard winner={winner} confidence={confidence} summary={summary} />
            ) : mode === 'analyst' && analystSummary && analystSummary.dimensionWins.length > 0 ? (
                <AnalystTopCard
                    summary={analystSummary}
                    dataQuality={dataQuality}
                    fallback={summary}
                />
            ) : (
                <NoWinnerCard summary={summary} />
            )}

            {!isAnalyst && scorecard && scorecard.vendors.length > 0 && (
                <>
                    <h2 style={sectionHeadingStyle}>Vendor comparison</h2>
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: scorecard.vendors.length >= 2 ? 'repeat(2, 1fr)' : '1fr',
                        gap: 14, marginBottom: 28,
                    }}>
                        {scorecard.vendors.map(v => (
                            <ScorecardCard
                                key={v}
                                vendor={v}
                                isWinner={hasWinner && v === winner}
                                dimensions={scorecard.dimensions}
                            />
                        ))}
                    </div>
                </>
            )}

            {!isAnalyst && tradeoffs && (tradeoffs.benefits.length > 0 || tradeoffs.sacrifices.length > 0) && (
                <>
                    <h2 style={sectionHeadingStyle}>Tradeoffs</h2>
                    <div style={{
                        display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 28,
                    }}>
                        {tradeoffs.benefits.map((b, i) =>
                            <TradeoffRow key={`b${i}`} icon="$" text={b} tone="success" />)}
                        {tradeoffs.sacrifices.map((s, i) =>
                            <TradeoffRow key={`s${i}`} icon="!" text={s} tone="warn" />)}
                    </div>
                </>
            )}

            {isAnalyst && analystMatrix && analystMatrix.vendors.length > 0 && (
                <>
                    <h2 style={sectionHeadingStyle}>Comparison matrix</h2>
                    <MatrixTable matrix={analystMatrix} />
                </>
            )}

            {isAnalyst && dimAnalysis.length > 0 && (
                <>
                    <h2 style={sectionHeadingStyle}>Dimension analysis</h2>
                    <div style={{
                        display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 28,
                    }}>
                        {dimAnalysis.map(d => <DimensionRow key={d.dimension} d={d} />)}
                    </div>
                </>
            )}

            {isAnalyst && vendorProfiles.length > 0 && (
                <>
                    <h2 style={sectionHeadingStyle}>Strengths &amp; weaknesses</h2>
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: `repeat(${Math.min(vendorProfiles.length, 3)}, 1fr)`,
                        gap: 14, marginBottom: 28,
                    }}>
                        {vendorProfiles.map(p => <VendorProfileCard key={p.vendor} profile={p} />)}
                    </div>
                </>
            )}

            {isAnalyst && bestFit.length > 0 && (
                <>
                    <h2 style={sectionHeadingStyle}>Best fit scenarios</h2>
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: `repeat(${Math.min(bestFit.length, 3)}, 1fr)`,
                        gap: 14, marginBottom: 28,
                    }}>
                        {bestFit.map(b => <BestFitCard key={b.vendor} b={b} />)}
                    </div>
                </>
            )}

            {isBuyer && dimBreakdown.length > 0 && (
                <>
                    <h2 style={sectionHeadingStyle}>Dimension breakdown</h2>
                    <div style={{
                        display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 28,
                    }}>
                        {dimBreakdown.map(d => <BuyerDimensionRow key={d.name} d={d} />)}
                    </div>
                </>
            )}

            {isBuyer && runnerUp && runnerUp.vendor && (
                <>
                    <h2 style={sectionHeadingStyle}>Runner-up</h2>
                    <RunnerUpCard r={runnerUp} />
                </>
            )}

            {isBuyer && questions.length > 0 && (
                <>
                    <h2 style={sectionHeadingStyle}>Questions to ask</h2>
                    <QuestionsCard questions={questions} />
                </>
            )}

            {isBuyer && nextSteps.length > 0 && (
                <>
                    <h2 style={sectionHeadingStyle}>Recommended next steps</h2>
                    <NextStepsCard steps={nextSteps} />
                </>
            )}

            {isBuyer && confBreakdown && confBreakdown.overall > 0 && (
                <>
                    <h2 style={sectionHeadingStyle}>Confidence breakdown</h2>
                    <ConfidenceBreakdownCard cb={confBreakdown} />
                </>
            )}

            {!isAnalyst && !isBuyer && (
                <>
                    <h2 style={sectionHeadingStyle}>Full report</h2>
                    <div style={{
                        background: 'var(--surface-1)', border: '1px solid var(--line)',
                        borderRadius: 14, padding: '24px 28px', marginBottom: 40,
                    }}>
                        <ReactMarkdown components={mdComponents}>{content}</ReactMarkdown>
                    </div>
                </>
            )}
        </div>
    );
}

/* ─── Buyer body components ─────────────────────── */

function BuyerDimensionRow({
    d,
}: { d: import('../lib/reportParser').DimensionDetail }) {
    return (
        <div style={{
            background: 'var(--surface-1)',
            border: `1px solid ${d.isPriority ? 'var(--warn-30)' : 'var(--line)'}`,
            borderRadius: 12, padding: '14px 16px',
        }}>
            <div style={{
                display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, flexWrap: 'wrap',
            }}>
                <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
                    color: d.isPriority ? 'var(--warn)' : 'var(--text-3)',
                    textTransform: 'uppercase', letterSpacing: '0.04em',
                }}>{d.name}</span>
                {d.isPriority && (
                    <span style={{
                        fontSize: 10, padding: '2px 8px', borderRadius: 100,
                        background: 'var(--warn-15)', color: 'var(--warn)',
                        fontWeight: 700, letterSpacing: '0.04em',
                    }}>TOP PRIORITY</span>
                )}
                {d.winner && (
                    <span style={{
                        fontSize: 11, padding: '2px 8px', borderRadius: 100,
                        background: 'var(--success-15)', color: 'var(--success)',
                        fontWeight: 700,
                    }}>Winner: {d.winner}</span>
                )}
            </div>
            {d.why && (
                <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-2)' }}>
                    {d.why}
                </div>
            )}
        </div>
    );
}

function RunnerUpCard({
    r,
}: { r: import('../lib/reportParser').RunnerUpData }) {
    return (
        <div style={{
            background: 'var(--surface-1)', border: '1px solid var(--line)',
            borderRadius: 14, padding: 20, marginBottom: 28,
            display: 'flex', gap: 18, alignItems: 'flex-start',
        }}>
            <div style={{
                width: 44, height: 44, borderRadius: 12,
                background: 'var(--surface-2)', border: '1px solid var(--line-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 700,
                color: 'var(--text-2)', flexShrink: 0,
            }}>2nd</div>
            <div style={{ flex: 1 }}>
                <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>{r.vendor}</div>
                {r.reason && (
                    <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.6, marginBottom: 8 }}>
                        {r.reason}
                    </div>
                )}
                {r.swingFactor && (
                    <div style={{
                        fontSize: 12, color: 'var(--text-3)',
                        borderLeft: '2px solid var(--accent-30)', paddingLeft: 10,
                    }}>
                        <span style={{ fontWeight: 700, color: 'var(--accent)' }}>Swing factor: </span>
                        {r.swingFactor}
                    </div>
                )}
            </div>
        </div>
    );
}

function QuestionsCard({ questions }: { questions: string[] }) {
    return (
        <div style={{
            background: 'var(--surface-1)', border: '1px solid var(--line)',
            borderRadius: 14, padding: '18px 20px', marginBottom: 28,
        }}>
            <ol style={{
                margin: 0, paddingLeft: 22, color: 'var(--text-2)',
                fontSize: 13, lineHeight: 1.7,
            }}>
                {questions.map((q, i) => (
                    <li key={i} style={{ marginBottom: 6 }}>{q}</li>
                ))}
            </ol>
        </div>
    );
}

function NextStepsCard({ steps }: { steps: string[] }) {
    return (
        <div style={{
            background: 'var(--surface-1)', border: '1px solid var(--line)',
            borderRadius: 14, padding: '18px 20px', marginBottom: 28,
        }}>
            {steps.map((s, i) => (
                <div key={i} style={{
                    display: 'flex', gap: 12, alignItems: 'center',
                    padding: '10px 0',
                    borderBottom: i === steps.length - 1 ? 'none' : '1px solid var(--surface-3)',
                }}>
                    <span style={{
                        width: 26, height: 26, borderRadius: 8, flexShrink: 0,
                        background: 'var(--accent-12)', color: 'var(--accent)',
                        fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>{i + 1}</span>
                    <span style={{ fontSize: 13, color: 'var(--text-2)' }}>{s}</span>
                </div>
            ))}
        </div>
    );
}

function ConfidenceBreakdownCard({
    cb,
}: { cb: import('../lib/reportParser').ConfidenceData }) {
    return (
        <div style={{
            background: 'var(--surface-1)', border: '1px solid var(--line)',
            borderRadius: 14, padding: 20, marginBottom: 40,
            display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 24, alignItems: 'center',
        }}>
            <div style={{ textAlign: 'center', minWidth: 100 }}>
                <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 32, fontWeight: 700,
                    color: 'var(--accent)',
                }}>{cb.overall}%</div>
                {cb.label && (
                    <div style={{
                        fontSize: 10, marginTop: 4, padding: '2px 8px', borderRadius: 100,
                        background: 'var(--accent-12)', color: 'var(--accent)',
                        fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',
                        display: 'inline-block',
                    }}>{cb.label}</div>
                )}
            </div>
            <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16,
                borderLeft: '1px solid var(--line)', paddingLeft: 22,
            }}>
                <ConfMetric label="Dimensions won" value={cb.dimensionsWon} />
                <ConfMetric label="Priority won" value={cb.priorityWon ? 'Yes' : 'No'}
                    tone={cb.priorityWon ? 'success' : 'warn'} />
                <ConfMetric label="Dominance" value={cb.dominance} />
            </div>
        </div>
    );
}

function ConfMetric({
    label, value, tone,
}: { label: string; value: string; tone?: 'success' | 'warn' }) {
    const color = tone === 'success' ? 'var(--success)' :
                  tone === 'warn' ? 'var(--warn)' : 'var(--text)';
    return (
        <div>
            <div style={{
                fontSize: 10, color: 'var(--text-3)', fontWeight: 700,
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4,
            }}>{label}</div>
            <div style={{
                fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 700, color,
            }}>{value || '—'}</div>
        </div>
    );
}

/* ─── Analyst body components ────────────────────── */

function MatrixTable({
    matrix,
}: { matrix: import('../lib/reportParser').ScorecardData }) {
    return (
        <div style={{
            background: 'var(--surface-1)', border: '1px solid var(--line)',
            borderRadius: 14, padding: '18px 20px', marginBottom: 28, overflowX: 'auto',
        }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                    <tr>
                        <th style={matrixThStyle}>Dimension</th>
                        {matrix.vendors.map(v => (
                            <th key={v} style={matrixThStyle}>{v}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {matrix.dimensions.map(d => (
                        <tr key={d.name}>
                            <td style={{ ...matrixTdStyle, color: 'var(--text-2)' }}>{d.name}</td>
                            {matrix.vendors.map(v => (
                                <td key={v} style={matrixTdStyle}>
                                    {d.results[v] ? (
                                        <span style={{
                                            fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
                                            color: 'var(--success)', padding: '3px 9px', borderRadius: 100,
                                            background: 'var(--success-15)',
                                        }}>WIN</span>
                                    ) : (
                                        <span style={{ color: 'var(--text-4)' }}>—</span>
                                    )}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function DimensionRow({
    d,
}: { d: import('../lib/reportParser').DimensionAnalysis }) {
    return (
        <div style={{
            background: 'var(--surface-1)', border: '1px solid var(--line)',
            borderRadius: 12, padding: '14px 16px',
        }}>
            <div style={{
                display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6,
            }}>
                <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
                    color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.04em',
                }}>{d.dimension}</span>
                {d.leader && (
                    <span style={{
                        fontSize: 11, padding: '2px 8px', borderRadius: 100,
                        background: 'var(--accent-12)', color: 'var(--accent)',
                        fontWeight: 700,
                    }}>Leader: {d.leader}</span>
                )}
            </div>
            {d.analysis && (
                <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-2)' }}>
                    {d.analysis}
                </div>
            )}
        </div>
    );
}

function VendorProfileCard({
    profile,
}: { profile: import('../lib/reportParser').VendorProfile }) {
    return (
        <div style={{
            background: 'var(--surface-1)', border: '1px solid var(--line)',
            borderRadius: 14, padding: 18,
        }}>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>
                {profile.vendor}
            </div>

            <div style={{
                fontSize: 10, fontWeight: 700, color: 'var(--success)',
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6,
            }}>Strengths</div>
            {profile.strengths.length > 0 ? (
                <ul style={{ margin: '0 0 12px', paddingLeft: 16, fontSize: 12.5, color: 'var(--text-2)' }}>
                    {profile.strengths.map(s => <li key={s} style={{ marginBottom: 3 }}>{s}</li>)}
                </ul>
            ) : (
                <div style={{ fontSize: 12, color: 'var(--text-4)', marginBottom: 12 }}>—</div>
            )}

            <div style={{
                fontSize: 10, fontWeight: 700, color: 'var(--warn)',
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6,
            }}>Weaknesses</div>
            {profile.weaknesses.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12.5, color: 'var(--text-2)' }}>
                    {profile.weaknesses.map(w => <li key={w} style={{ marginBottom: 3 }}>{w}</li>)}
                </ul>
            ) : (
                <div style={{ fontSize: 12, color: 'var(--text-4)' }}>—</div>
            )}
        </div>
    );
}

function BestFitCard({
    b,
}: { b: import('../lib/reportParser').BestFitScenario }) {
    return (
        <div style={{
            background: 'var(--surface-1)', border: '1px solid var(--line)',
            borderRadius: 14, padding: 18,
        }}>
            <div style={{
                fontSize: 10, fontWeight: 700, color: 'var(--accent)',
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4,
            }}>Choose</div>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>{b.vendor}</div>
            <div style={{
                fontSize: 10, fontWeight: 700, color: 'var(--text-3)',
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6,
            }}>If</div>
            <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.6 }}>
                {b.conditions.map((c, i) => <li key={i} style={{ marginBottom: 4 }}>{c}</li>)}
            </ul>
        </div>
    );
}

const matrixThStyle: React.CSSProperties = {
    padding: '8px 10px', textAlign: 'left', fontSize: 11, fontWeight: 700,
    color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em',
    borderBottom: '1px solid var(--line)',
};
const matrixTdStyle: React.CSSProperties = {
    padding: '10px', fontSize: 13,
    borderBottom: '1px solid var(--surface-3)',
};

/* ─── Cards ───────────────────────────────────── */

function WinnerCard({
    winner, confidence, summary,
}: { winner: string; confidence: number; summary: string }) {
    return (
        <div style={{
            background: 'linear-gradient(135deg, var(--success-12), var(--surface-1))',
            border: '1px solid var(--success-30)',
            borderRadius: 18, padding: 28, marginBottom: 24,
            display: 'flex', alignItems: 'center', gap: 22,
        }}>
            <div style={{
                width: 56, height: 56, borderRadius: 14,
                background: 'var(--success-15)',
                border: '1px solid var(--success-30)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700,
                color: 'var(--success)', flexShrink: 0,
            }}>W</div>
            <div style={{ flex: 1 }}>
                <div style={{
                    fontSize: 12, color: 'var(--success)', fontWeight: 700,
                    textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4,
                }}>Recommended winner</div>
                <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.01em' }}>{winner}</div>
                {summary && (
                    <div style={{ fontSize: 13, color: 'var(--text-3)', marginTop: 6 }}>{summary}</div>
                )}
            </div>
            <div style={{ textAlign: 'center', flexShrink: 0 }}>
                <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 30, fontWeight: 700,
                    color: 'var(--success)',
                }}>{confidence ? `${confidence}%` : '—'}</div>
                <div style={{ fontSize: 11, color: 'var(--text-3)' }}>confidence</div>
            </div>
        </div>
    );
}

function AnalystTopCard({
    summary, dataQuality, fallback,
}: {
    summary: import('../lib/reportParser').AnalystSummary;
    dataQuality: import('../lib/reportParser').DataQuality | null;
    fallback: string;
}) {
    const total = summary.dimensionWins[0]?.total || 0;
    // e.g. "10.0/10 (High)" -> qualityPct = 100, qualityLabel = "High"
    const qMatch = dataQuality?.score.match(/(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)(?:\s*\(([^)]+)\))?/);
    const qualityPct   = qMatch ? Math.round((parseFloat(qMatch[1]) / parseFloat(qMatch[2])) * 100) : null;
    const qualityLabel = qMatch?.[3] || '';

    return (
        <div style={{
            background: 'linear-gradient(135deg, var(--accent-12), var(--surface-1))',
            border: '1px solid var(--accent-30)',
            borderRadius: 18, padding: 28, marginBottom: 24,
            display: 'grid', gridTemplateColumns: '1fr auto', gap: 24, alignItems: 'center',
        }}>
            <div>
                <div style={{
                    fontSize: 12, color: 'var(--accent)', fontWeight: 700,
                    textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 10,
                }}>Market comparison — no single winner declared</div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 6 }}>
                    {summary.dimensionWins.map(w => {
                        const pct = total ? (w.wins / total) * 100 : 0;
                        return (
                            <div key={w.vendor} style={{
                                display: 'grid',
                                gridTemplateColumns: '140px 1fr 56px',
                                alignItems: 'center', gap: 12,
                            }}>
                                <span style={{ fontSize: 14, fontWeight: 700, letterSpacing: '-0.01em' }}>
                                    {w.vendor}
                                </span>
                                <div style={{
                                    height: 8, borderRadius: 4, background: 'oklch(1 0 0 / 0.07)',
                                }}>
                                    <div style={{
                                        height: '100%', borderRadius: 4, width: `${pct}%`,
                                        background: 'var(--accent)',
                                        transition: 'width 0.3s',
                                    }} />
                                </div>
                                <span style={{
                                    fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700,
                                    color: 'var(--text-2)', textAlign: 'right',
                                }}>{w.wins}/{w.total}</span>
                            </div>
                        );
                    })}
                </div>

                {(summary.description || fallback) && (
                    <div style={{ fontSize: 13, color: 'var(--text-3)', marginTop: 12 }}>
                        {summary.description || fallback}
                    </div>
                )}
            </div>

            <div style={{
                textAlign: 'center', flexShrink: 0, borderLeft: '1px solid var(--line)',
                paddingLeft: 22, minWidth: 110,
            }}>
                <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 30, fontWeight: 700,
                    color: 'var(--accent)',
                }}>{qualityPct != null ? `${qualityPct}%` : '—'}</div>
                <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
                    data quality
                </div>
                {qualityLabel && (
                    <div style={{
                        fontSize: 10, marginTop: 6, padding: '2px 8px', borderRadius: 100,
                        background: 'var(--accent-12)', color: 'var(--accent)',
                        fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',
                        display: 'inline-block',
                    }}>{qualityLabel}</div>
                )}
            </div>
        </div>
    );
}

function NoWinnerCard({ summary }: { summary: string }) {
    return (
        <div style={{
            background: 'var(--surface-1)',
            border: '1px solid var(--line)',
            borderRadius: 18, padding: 28, marginBottom: 24,
            display: 'flex', alignItems: 'center', gap: 22,
        }}>
            <div style={{
                width: 56, height: 56, borderRadius: 14,
                background: 'var(--surface-2)',
                border: '1px solid var(--line-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700,
                color: 'var(--text-3)', flexShrink: 0,
            }}>=</div>
            <div style={{ flex: 1 }}>
                <div style={{
                    fontSize: 12, color: 'var(--text-3)', fontWeight: 700,
                    textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4,
                }}>No winner declared</div>
                <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.01em' }}>
                    Neutral comparison — analyst mode
                </div>
                {summary && (
                    <div style={{ fontSize: 13, color: 'var(--text-3)', marginTop: 6 }}>{summary}</div>
                )}
            </div>
        </div>
    );
}

function ScorecardCard({
    vendor, isWinner, dimensions,
}: {
    vendor: string;
    isWinner: boolean;
    dimensions: { name: string; results: Record<string, boolean> }[];
}) {
    return (
        <div style={{
            background: 'var(--surface-1)',
            border: `1px solid ${isWinner ? 'var(--success-30)' : 'var(--line)'}`,
            borderRadius: 14, padding: 20,
        }}>
            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: 14,
            }}>
                <span style={{ fontSize: 15, fontWeight: 700 }}>{vendor}</span>
                {isWinner && (
                    <span style={{
                        fontSize: 11, padding: '3px 9px', borderRadius: 100,
                        background: 'var(--success-15)', color: 'var(--success)',
                        fontWeight: 700,
                    }}>WINNER</span>
                )}
            </div>
            {dimensions.map(d => {
                const win = !!d.results[vendor];
                const pct = win ? 85 : 45;
                return (
                    <div key={d.name} style={{ marginBottom: 9 }}>
                        <div style={{
                            display: 'flex', justifyContent: 'space-between',
                            fontSize: 11, color: 'var(--text-3)', marginBottom: 3,
                        }}>
                            <span>{d.name}</span>
                            <span style={{ fontFamily: 'var(--font-mono)' }}>
                                {win ? 'win' : 'lose'}
                            </span>
                        </div>
                        <div style={{
                            height: 5, borderRadius: 4, background: 'oklch(1 0 0 / 0.07)',
                        }}>
                            <div style={{
                                height: '100%', borderRadius: 4, width: `${pct}%`,
                                background: win ? 'var(--success)' : 'var(--accent)',
                            }} />
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function TradeoffRow({
    icon, text, tone,
}: { icon: string; text: string; tone: 'success' | 'warn' }) {
    const bg = tone === 'success' ? 'var(--success-15)' : 'var(--warn-15)';
    const color = tone === 'success' ? 'var(--success)' : 'var(--warn)';
    return (
        <div style={{
            display: 'flex', gap: 12,
            background: 'var(--surface-1)', border: '1px solid var(--line)',
            borderRadius: 12, padding: '14px 16px',
        }}>
            <span style={{
                width: 22, height: 22, borderRadius: 6,
                background: bg, color, fontFamily: 'var(--font-mono)',
                fontSize: 12, fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
            }}>{icon}</span>
            <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-2)' }}>{text}</div>
        </div>
    );
}

/* ─── Helpers ─────────────────────────────────── */

function buildProfilePills(
    profile: ReturnType<typeof extractProfile>,
    mode: string,
    vendorCount: number | undefined,
): string[] {
    const pills: string[] = [`Mode: ${mode}`];
    if (typeof vendorCount === 'number' && vendorCount > 0) {
        pills.push(`${vendorCount} vendors compared`);
    }
    if (!profile) return pills;
    if (profile.company)  pills.push(profile.company);
    if (profile.team)     pills.push(profile.team);
    if (profile.budget)   pills.push(profile.budget);
    if (profile.useCase)  pills.push(profile.useCase);
    if (profile.priority) pills.push(`${profile.priority} priority`);
    return pills;
}

const sectionHeadingStyle: React.CSSProperties = {
    fontSize: 16, fontWeight: 700, margin: '0 0 14px',
};

const mdComponents = {
    h1: (p: { children?: React.ReactNode }) => (
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '4px 0 12px' }}>{p.children}</h1>
    ),
    h2: (p: { children?: React.ReactNode }) => (
        <h2 style={{
            fontSize: 15, fontWeight: 700, color: 'var(--accent)',
            margin: '20px 0 8px',
        }}>{p.children}</h2>
    ),
    h3: (p: { children?: React.ReactNode }) => (
        <h3 style={{
            fontSize: 14, fontWeight: 700, color: 'var(--accent)',
            margin: '16px 0 8px',
        }}>{p.children}</h3>
    ),
    p: (p: { children?: React.ReactNode }) => (
        <p style={{
            fontSize: 13, lineHeight: 1.7, color: 'var(--text-2)', margin: '0 0 12px',
        }}>{p.children}</p>
    ),
    ul: (p: { children?: React.ReactNode }) => (
        <ul style={{
            fontSize: 13, lineHeight: 1.7, color: 'var(--text-2)',
            margin: '0 0 12px', paddingLeft: 20,
        }}>{p.children}</ul>
    ),
    ol: (p: { children?: React.ReactNode }) => (
        <ol style={{
            fontSize: 13, lineHeight: 1.7, color: 'var(--text-2)',
            margin: '0 0 12px', paddingLeft: 20,
        }}>{p.children}</ol>
    ),
    li: (p: { children?: React.ReactNode }) => (
        <li style={{ marginBottom: 4 }}>{p.children}</li>
    ),
    a: (p: { href?: string; children?: React.ReactNode }) => (
        <a href={p.href} target="_blank" rel="noreferrer"
            style={{ color: 'var(--accent)', textDecoration: 'underline' }}>{p.children}</a>
    ),
    code: (p: { children?: React.ReactNode }) => (
        <code style={{
            fontFamily: 'var(--font-mono)', fontSize: 12,
            background: 'var(--surface-2)', padding: '2px 6px', borderRadius: 4,
        }}>{p.children}</code>
    ),
    table: (p: { children?: React.ReactNode }) => (
        <div style={{ overflowX: 'auto', margin: '0 0 12px' }}>
            <table style={{
                width: '100%', borderCollapse: 'collapse', fontSize: 12,
            }}>{p.children}</table>
        </div>
    ),
    th: (p: { children?: React.ReactNode }) => (
        <th style={{
            padding: '8px 10px', textAlign: 'left', fontWeight: 700,
            color: 'var(--text)', borderBottom: '1px solid var(--line)',
        }}>{p.children}</th>
    ),
    td: (p: { children?: React.ReactNode }) => (
        <td style={{
            padding: '8px 10px', color: 'var(--text-2)',
            borderBottom: '1px solid var(--surface-3)',
        }}>{p.children}</td>
    ),
};
