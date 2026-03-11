import {
    extractProfile,
    extractScorecard,
    extractDimensionBreakdown,
    extractTradeoffs,
    extractRunnerUp,
    extractQuestions,
    extractConfidenceBreakdown,
    extractBuyerNextSteps,
    extractAdvantages,
    extractVulnerabilities,
    extractLandmines,
    extractTalkTrack,
    extractDoNotSay,
    extractObjectionHandling,
    extractSellerNextSteps,
    extractAnalystSummary,
    extractAnalystMatrix,
    extractDimensionAnalysis,
    extractVendorProfiles,
    extractBestFitScenarios,
    extractAnalystTradeoffs,
    extractDataQuality,
    extractMethodology,
} from '../../lib/reportParser';
import type { ReportMode } from '../../lib/reportParser';
import { ProfilePills } from './ProfilePills';
import { VendorScorecard } from './VendorScorecard';
import { TradeoffsSection } from './TradeoffsSection';
import { SectionHeader } from './SectionHeader';
import { AnalystHeader } from './AnalystHeader';
import { MethodologyNote } from './MethodologyNote';

interface ReportBodyProps {
    content: string;
    mode: ReportMode;
}

export function ReportBody({ content, mode }: ReportBodyProps) {
    if (mode === 'buyer') return <BuyerBody content={content} />;
    if (mode === 'seller') return <SellerBody content={content} />;
    if (mode === 'analyst') return <AnalystBody content={content} />;
    return <BuyerBody content={content} />;
}

// ─── Buyer Layout ──────────────────────────────────────────────

function BuyerBody({ content }: { content: string }) {
    const profile = extractProfile(content);
    const scorecard = extractScorecard(content);
    const dimensions = extractDimensionBreakdown(content);
    const tradeoffs = extractTradeoffs(content);
    const runnerUp = extractRunnerUp(content);
    const questions = extractQuestions(content);
    const confidence = extractConfidenceBreakdown(content);
    const nextSteps = extractBuyerNextSteps(content);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Profile Pills */}
            {profile && <ProfilePills profile={profile} label="Your Requirements" />}

            {/* Vendor Scorecard + Dimension Breakdown */}
            {scorecard && (
                <VendorScorecard
                    scorecard={scorecard}
                    dimensions={dimensions}
                    priority={profile?.priority}
                />
            )}

            {/* Tradeoffs */}
            {tradeoffs && <TradeoffsSection tradeoffs={tradeoffs} />}

            {/* Runner Up */}
            {runnerUp && runnerUp.vendor && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="🥈" title="RUNNER UP" />
                    <div style={{
                        background: '#12121a', border: '1px solid #2a2a3a',
                        borderRadius: '8px', padding: '12px 16px'
                    }}>
                        <div style={{ fontSize: '14px', color: '#ffffff' }}>
                            <strong>{runnerUp.vendor}</strong>
                            {runnerUp.reason && (
                                <span style={{ color: '#8a8a9a' }}> — {runnerUp.reason}</span>
                            )}
                        </div>
                        {runnerUp.swingFactor && (
                            <div style={{ fontSize: '12px', color: '#8a8a9a', marginTop: '8px' }}>
                                <span style={{ color: '#ffaa00' }}>Swing Factor:</span> {runnerUp.swingFactor}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Questions */}
            {questions.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="❓" title="QUESTIONS TO ASK BEFORE SIGNING" />
                    <div style={{
                        borderLeft: '2px solid #2a2a3a',
                        paddingLeft: '16px',
                        display: 'flex', flexDirection: 'column', gap: '8px'
                    }}>
                        {questions.map((q, i) => (
                            <div key={i} style={{ fontSize: '13px', color: '#e0e0e0', lineHeight: '1.4' }}>
                                <span style={{ color: '#8a8a9a', marginRight: '8px' }}>{i + 1}.</span>
                                {q}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Confidence Breakdown */}
            {confidence && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="📋" title="CONFIDENCE BREAKDOWN" />
                    <div style={{
                        background: '#12121a', border: '1px solid #2a2a3a',
                        borderRadius: '8px', padding: '12px 16px',
                        display: 'flex', gap: '24px', flexWrap: 'wrap', fontSize: '13px'
                    }}>
                        <div>
                            <span style={{ color: '#8a8a9a' }}>Overall: </span>
                            <span style={{ color: '#ffffff', fontWeight: 600 }}>{confidence.overall}% ({confidence.label})</span>
                        </div>
                        <div>
                            <span style={{ color: '#8a8a9a' }}>Dimensions Won: </span>
                            <span style={{ color: '#ffffff' }}>{confidence.dimensionsWon}</span>
                        </div>
                        <div>
                            <span style={{ color: '#8a8a9a' }}>Priority Won: </span>
                            <span style={{ color: confidence.priorityWon ? '#00ff88' : '#ff4466' }}>
                                {confidence.priorityWon ? 'Yes ✅' : 'No ❌'}
                            </span>
                        </div>
                        <div>
                            <span style={{ color: '#8a8a9a' }}>Dominance: </span>
                            <span style={{ color: '#ffffff' }}>{confidence.dominance}</span>
                        </div>
                    </div>
                </div>
            )}

            {/* Next Steps */}
            {nextSteps.length > 0 && (
                <div>
                    <SectionHeader icon="🚀" title="RECOMMENDED NEXT STEPS" />
                    <div style={{
                        borderLeft: '2px solid #2a2a3a',
                        paddingLeft: '16px',
                        display: 'flex', flexDirection: 'column', gap: '6px'
                    }}>
                        {nextSteps.map((s, i) => (
                            <div key={i} style={{ fontSize: '13px', color: '#e0e0e0' }}>
                                <span style={{ color: '#00d4ff', marginRight: '8px' }}>{i + 1}.</span>
                                {s}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// ─── Seller Layout ─────────────────────────────────────────────

function SellerBody({ content }: { content: string }) {
    const profile = extractProfile(content);
    const advantages = extractAdvantages(content);
    const vulnerabilities = extractVulnerabilities(content);
    const landmines = extractLandmines(content);
    const talkTrack = extractTalkTrack(content);
    const doNotSay = extractDoNotSay(content);
    const objections = extractObjectionHandling(content);
    const nextSteps = extractSellerNextSteps(content);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Target Prospect */}
            {profile && <ProfilePills profile={profile} label="Target Prospect" />}

            {/* Advantages */}
            {advantages.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="💪" title="YOUR ADVANTAGES (Lead with these)" color="#00ff88" />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {advantages.map((adv, i) => (
                            <div key={i} style={{
                                background: adv.isPriority ? 'rgba(0, 255, 136, 0.06)' : '#12121a',
                                border: `1px solid ${adv.isPriority ? 'rgba(0, 255, 136, 0.2)' : '#2a2a3a'}`,
                                borderLeft: adv.isPriority ? '3px solid #00ff88' : '3px solid #2a2a3a',
                                borderRadius: '6px', padding: '12px'
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                                    <span style={{ color: '#ffffff', fontSize: '14px', fontWeight: 600 }}>{adv.title}</span>
                                    {adv.isPriority && (
                                        <span style={{
                                            background: 'rgba(255, 170, 0, 0.15)', color: '#ffaa00',
                                            padding: '1px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600
                                        }}>
                                            ⭐ Their Priority
                                        </span>
                                    )}
                                </div>
                                {adv.quote && (
                                    <div style={{ color: '#8a8a9a', fontSize: '13px', fontStyle: 'italic', marginBottom: '6px' }}>
                                        "{adv.quote}"
                                    </div>
                                )}
                                {adv.tip && (
                                    <div style={{ color: '#00ff88', fontSize: '12px', fontWeight: 600 }}>
                                        → {adv.tip}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Vulnerabilities */}
            {vulnerabilities.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="⚠️" title="YOUR VULNERABILITIES (Prepare for these)" color="#ffaa00" />
                    <div style={{
                        borderLeft: '2px solid rgba(255, 170, 0, 0.3)',
                        paddingLeft: '16px',
                        display: 'flex', flexDirection: 'column', gap: '8px'
                    }}>
                        {vulnerabilities.map((v, i) => (
                            <div key={i} style={{
                                fontSize: '13px', color: '#e0e0e0', lineHeight: '1.4'
                            }}>
                                <span style={{ color: '#ffaa00' }}>⚠️</span>{' '}
                                <strong>{v.title}</strong>
                                {v.competitor && (
                                    <span style={{ color: '#8a8a9a' }}> — {v.competitor} is stronger here</span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Landmines */}
            {landmines && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="💣" title="COMPETITOR LANDMINES (Neutralize these)" color="#ff4466" />
                    <div style={{
                        background: 'rgba(255, 68, 102, 0.04)',
                        border: '1px solid rgba(255, 68, 102, 0.15)',
                        borderRadius: '8px', padding: '14px'
                    }}>
                        {landmines.theySay.length > 0 && (
                            <div style={{ marginBottom: '12px' }}>
                                <div style={{ fontSize: '12px', color: '#ff4466', fontWeight: 700, marginBottom: '6px' }}>
                                    IF THEY SAY:
                                </div>
                                {landmines.theySay.map((t, i) => (
                                    <div key={i} style={{
                                        fontSize: '13px', color: '#8a8a9a', fontStyle: 'italic', marginBottom: '4px'
                                    }}>
                                        "{t}"
                                    </div>
                                ))}
                            </div>
                        )}
                        {landmines.youSay && (
                            <div>
                                <div style={{ fontSize: '12px', color: '#00ff88', fontWeight: 700, marginBottom: '6px' }}>
                                    YOU SAY:
                                </div>
                                <div style={{
                                    fontSize: '13px', color: '#e0e0e0', lineHeight: '1.5',
                                    background: '#12121a', borderRadius: '6px', padding: '10px 12px',
                                    borderLeft: '2px solid #00ff88'
                                }}>
                                    {landmines.youSay}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Talk Track */}
            {talkTrack && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="🗣️" title="TALK TRACK FOR THIS DEAL" color="#aa66ff" />
                    <div style={{
                        background: 'rgba(170, 102, 255, 0.04)',
                        border: '1px solid rgba(170, 102, 255, 0.15)',
                        borderLeft: '3px solid #aa66ff',
                        borderRadius: '8px', padding: '16px',
                        display: 'flex', flexDirection: 'column', gap: '14px'
                    }}>
                        {talkTrack.opening && (
                            <div>
                                <div style={{ fontSize: '11px', color: '#aa66ff', fontWeight: 700, marginBottom: '6px' }}>OPENING</div>
                                <div style={{ fontSize: '15px', color: '#e0e0e0', fontStyle: 'italic', lineHeight: '1.6' }}>
                                    "{talkTrack.opening}"
                                </div>
                            </div>
                        )}
                        {talkTrack.keyPoints.length > 0 && (
                            <div>
                                <div style={{ fontSize: '11px', color: '#aa66ff', fontWeight: 700, marginBottom: '6px' }}>KEY POINTS</div>
                                {talkTrack.keyPoints.map((kp, i) => (
                                    <div key={i} style={{ fontSize: '14px', color: '#e0e0e0', marginBottom: '6px', lineHeight: '1.5' }}>
                                        <span style={{ color: '#aa66ff', marginRight: '6px' }}>{i + 1}.</span> {kp}
                                    </div>
                                ))}
                            </div>
                        )}
                        {talkTrack.close && (
                            <div>
                                <div style={{ fontSize: '11px', color: '#aa66ff', fontWeight: 700, marginBottom: '6px' }}>CLOSE</div>
                                <div style={{ fontSize: '15px', color: '#e0e0e0', fontStyle: 'italic', lineHeight: '1.6' }}>
                                    "{talkTrack.close}"
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Do Not Say */}
            {doNotSay.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="🚫" title="DO NOT SAY" color="#ff4466" />
                    <div style={{
                        background: 'rgba(255, 68, 102, 0.06)',
                        border: '1px solid rgba(255, 68, 102, 0.15)',
                        borderRadius: '8px',
                        padding: '14px',
                        display: 'flex', flexDirection: 'column', gap: '8px'
                    }}>
                        {doNotSay.map((item, i) => (
                            <div key={i} style={{ fontSize: '13px', color: '#ff4466', lineHeight: '1.4' }}>
                                <span style={{ fontWeight: 700, marginRight: '6px' }}>✗</span>{item}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Objection Handling */}
            {objections.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="🛡️" title="OBJECTION HANDLING" />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {objections.map((obj, i) => (
                            <div key={i} style={{
                                background: '#12121a', border: '1px solid #2a2a3a',
                                borderRadius: '8px', padding: '12px'
                            }}>
                                <div style={{ fontSize: '13px', color: '#ffaa00', marginBottom: '6px' }}>
                                    <strong>Objection:</strong> "{obj.objection}"
                                </div>
                                <div style={{ fontSize: '13px', color: '#00ff88' }}>
                                    <strong>Response:</strong> "{obj.response}"
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Next Steps */}
            {nextSteps.length > 0 && (
                <div>
                    <SectionHeader icon="📞" title="NEXT STEPS FOR THIS DEAL" />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                        {nextSteps.map((group, i) => (
                            <div key={i}>
                                <div style={{
                                    fontSize: '11px', color: '#00d4ff', fontWeight: 700,
                                    textTransform: 'uppercase', marginBottom: '6px'
                                }}>
                                    {group.phase}
                                </div>
                                <div style={{
                                    borderLeft: '2px solid #2a2a3a', paddingLeft: '12px',
                                    display: 'flex', flexDirection: 'column', gap: '4px'
                                }}>
                                    {group.items.map((item, j) => (
                                        <div key={j} style={{ fontSize: '13px', color: '#e0e0e0' }}>
                                            <span style={{ color: '#8a8a9a', marginRight: '6px' }}>☐</span>
                                            {item}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// ─── Analyst Layout ────────────────────────────────────────────

function AnalystBody({ content }: { content: string }) {
    const summary = extractAnalystSummary(content);
    const matrix = extractAnalystMatrix(content);
    const dimAnalysis = extractDimensionAnalysis(content);
    const vendorProfiles = extractVendorProfiles(content);
    const bestFit = extractBestFitScenarios(content);
    const tradeoffs = extractAnalystTradeoffs(content);
    const dataQuality = extractDataQuality(content);
    const methodology = extractMethodology(content);

    // Extract vertical from parsed title
    const verticalMatch = content.match(/║\s+(.+?)\s+║/m);
    const vertical = verticalMatch ? verticalMatch[1].replace(/📊|MARKET ANALYSIS REPORT/g, '').trim() : '';

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Analyst Header */}
            {summary && <AnalystHeader summary={summary} vertical={vertical} />}

            {/* Comparison Matrix */}
            {matrix && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="📊" title="COMPARISON MATRIX" />
                    <div style={{
                        background: '#12121a', border: '1px solid #2a2a3a',
                        borderRadius: '8px', overflow: 'hidden'
                    }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                            <thead>
                                <tr>
                                    <th style={{
                                        textAlign: 'left', padding: '10px 12px',
                                        background: '#1a1a24', color: '#00d4ff',
                                        fontWeight: 600, borderBottom: '1px solid #2a2a3a', fontSize: '12px'
                                    }}>
                                        Dimension
                                    </th>
                                    {matrix.vendors.map((v, i) => (
                                        <th key={i} style={{
                                            textAlign: 'center', padding: '10px 8px',
                                            background: '#1a1a24', color: '#8a8a9a',
                                            fontWeight: 600, borderBottom: '1px solid #2a2a3a', fontSize: '12px'
                                        }}>
                                            {v}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {matrix.dimensions.map((dim, i) => (
                                    <tr key={i} style={{ borderBottom: '1px solid #1f1f2e' }}>
                                        <td style={{ padding: '8px 12px', color: '#ffffff' }}>{dim.name}</td>
                                        {matrix.vendors.map((v, j) => (
                                            <td key={j} style={{
                                                textAlign: 'center', padding: '8px',
                                                color: dim.results[v] ? '#00ff88' : '#3a3a4a'
                                            }}>
                                                {dim.results[v] ? '✅' : '—'}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Dimension Analysis */}
            {dimAnalysis.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="📋" title="DIMENSION ANALYSIS" />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {dimAnalysis.map((dim, i) => (
                            <div key={i} style={{
                                background: '#12121a', border: '1px solid #1f1f2e',
                                borderLeft: '3px solid #00d4ff',
                                borderRadius: '6px', padding: '10px 12px'
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                                    <span style={{ color: '#ffffff', fontSize: '14px', fontWeight: 600 }}>{dim.dimension}</span>
                                    <span style={{
                                        background: 'rgba(0, 255, 136, 0.1)', color: '#00ff88',
                                        padding: '1px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600
                                    }}>
                                        {dim.leader}
                                    </span>
                                </div>
                                {dim.analysis && (
                                    <div style={{ color: '#8a8a9a', fontSize: '13px', lineHeight: '1.4' }}>
                                        {dim.analysis}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Vendor Profiles (Strengths & Weaknesses) */}
            {vendorProfiles.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="💪" title="STRENGTHS & WEAKNESSES BY VENDOR" />
                    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(vendorProfiles.length, 3)}, 1fr)`, gap: '12px' }}>
                        {vendorProfiles.map((vp, i) => (
                            <div key={i} style={{
                                background: '#12121a', border: '1px solid #2a2a3a',
                                borderRadius: '8px', padding: '14px'
                            }}>
                                <div style={{
                                    fontSize: '14px', fontWeight: 700, color: '#ffffff', marginBottom: '10px',
                                    paddingBottom: '8px', borderBottom: '1px solid #1f1f2e'
                                }}>
                                    {vp.vendor}
                                </div>
                                {vp.strengths.length > 0 && (
                                    <div style={{ marginBottom: '8px' }}>
                                        <div style={{ fontSize: '11px', color: '#00ff88', fontWeight: 700, marginBottom: '4px' }}>STRENGTHS</div>
                                        {vp.strengths.map((s, j) => (
                                            <div key={j} style={{ fontSize: '12px', color: '#e0e0e0', marginBottom: '2px' }}>
                                                <span style={{ color: '#00ff88', marginRight: '4px' }}>✅</span> {s}
                                            </div>
                                        ))}
                                    </div>
                                )}
                                {vp.weaknesses.length > 0 && (
                                    <div>
                                        <div style={{ fontSize: '11px', color: '#ffaa00', fontWeight: 700, marginBottom: '4px' }}>WEAKNESSES</div>
                                        {vp.weaknesses.map((w, j) => (
                                            <div key={j} style={{ fontSize: '12px', color: '#e0e0e0', marginBottom: '2px' }}>
                                                <span style={{ color: '#ffaa00', marginRight: '4px' }}>⚠️</span> {w}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Best Fit Scenarios */}
            {bestFit.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="🎯" title="BEST FIT SCENARIOS" />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {bestFit.map((bf, i) => (
                            <div key={i} style={{
                                background: '#12121a', border: '1px solid #2a2a3a',
                                borderRadius: '8px', padding: '12px'
                            }}>
                                <div style={{
                                    fontSize: '13px', fontWeight: 700, color: '#00d4ff', marginBottom: '8px'
                                }}>
                                    Choose {bf.vendor} if:
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                    {bf.conditions.map((c, j) => (
                                        <div key={j} style={{ fontSize: '13px', color: '#e0e0e0' }}>
                                            <span style={{ color: '#8a8a9a', marginRight: '6px' }}>•</span>{c}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Key Tradeoffs */}
            {tradeoffs.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="⚖️" title="KEY TRADEOFFS" />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {tradeoffs.map((to, i) => (
                            <div key={i} style={{
                                background: '#12121a', border: '1px solid #1f1f2e',
                                borderRadius: '6px', padding: '10px 12px'
                            }}>
                                <div style={{ fontSize: '13px', fontWeight: 600, color: '#ffaa00', marginBottom: '6px' }}>
                                    {to.title}
                                </div>
                                {to.lines.map((l, j) => (
                                    <div key={j} style={{ fontSize: '13px', color: '#8a8a9a', lineHeight: '1.4' }}>
                                        {l.startsWith('Choose') || l.startsWith('→')
                                            ? <span style={{ color: '#00d4ff' }}>→ {l.replace(/^→\s*/, '')}</span>
                                            : l
                                        }
                                    </div>
                                ))}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Data Quality Note */}
            {dataQuality && (
                <div style={{ marginBottom: '16px' }}>
                    <SectionHeader icon="📋" title="DATA QUALITY" />
                    <div style={{
                        background: '#12121a', border: '1px solid #2a2a3a',
                        borderRadius: '8px', padding: '12px 16px'
                    }}>
                        {dataQuality.score && (
                            <div style={{ fontSize: '14px', color: '#ffffff', marginBottom: '10px' }}>
                                Analysis Quality: <strong style={{ color: '#00ff88' }}>{dataQuality.score}</strong>
                            </div>
                        )}
                        {dataQuality.details.length > 0 && (
                            <div style={{ marginBottom: '10px' }}>
                                {dataQuality.details.map((d, i) => (
                                    <div key={i} style={{ fontSize: '12px', color: '#8a8a9a', marginBottom: '2px' }}>
                                        • {d}
                                    </div>
                                ))}
                            </div>
                        )}
                        {dataQuality.caveats.length > 0 && (
                            <div>
                                <div style={{ fontSize: '11px', color: '#ffaa00', fontWeight: 700, marginBottom: '4px' }}>CAVEATS</div>
                                {dataQuality.caveats.map((c, i) => (
                                    <div key={i} style={{ fontSize: '12px', color: '#8a8a9a', marginBottom: '2px' }}>
                                        ⚠️ {c}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Methodology */}
            <MethodologyNote steps={methodology} />
        </div>
    );
}
