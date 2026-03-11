import type { ScorecardData, DimensionDetail } from '../../lib/reportParser';
import { SectionHeader } from './SectionHeader';

interface VendorScorecardProps {
    scorecard: ScorecardData;
    dimensions: DimensionDetail[];
    priority?: string;
}

export function VendorScorecard({ scorecard, dimensions, priority }: VendorScorecardProps) {
    const { vendors } = scorecard;

    return (
        <div style={{ marginBottom: '16px' }}>
            <SectionHeader icon="📊" title="HOW VENDORS SCORED" />

            {/* Scorecard Table */}
            <div style={{
                background: '#12121a',
                border: '1px solid #2a2a3a',
                borderRadius: '8px',
                overflow: 'hidden',
                marginBottom: '12px'
            }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead>
                        <tr>
                            <th style={{
                                textAlign: 'left', padding: '10px 12px',
                                background: '#1a1a24', color: '#00d4ff',
                                fontWeight: 600, borderBottom: '1px solid #2a2a3a',
                                fontSize: '12px'
                            }}>
                                Dimension
                            </th>
                            {vendors.map((v, i) => (
                                <th key={i} style={{
                                    textAlign: 'center', padding: '10px 8px',
                                    background: '#1a1a24', color: '#8a8a9a',
                                    fontWeight: 600, borderBottom: '1px solid #2a2a3a',
                                    fontSize: '12px', whiteSpace: 'nowrap'
                                }}>
                                    {v}
                                </th>
                            ))}
                            <th style={{
                                textAlign: 'center', padding: '10px 12px',
                                background: '#1a1a24', color: '#00ff88',
                                fontWeight: 600, borderBottom: '1px solid #2a2a3a',
                                fontSize: '12px'
                            }}>
                                Winner
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {scorecard.dimensions.map((dim, i) => {
                            const isPrio = priority && dim.name.toLowerCase().includes(priority.toLowerCase());
                            const winner = vendors.find(v => dim.results[v]);
                            const detail = dimensions.find(d =>
                                d.name.toLowerCase() === dim.name.toLowerCase()
                            );

                            return (
                                <tr key={i} style={{
                                    borderBottom: i < scorecard.dimensions.length - 1 ? '1px solid #1f1f2e' : 'none',
                                    background: isPrio ? 'rgba(255, 170, 0, 0.05)' : 'transparent'
                                }}>
                                    <td style={{
                                        padding: '8px 12px', color: '#ffffff',
                                        fontWeight: isPrio ? 600 : 400
                                    }}>
                                        {isPrio && <span style={{ marginRight: '4px' }}>⭐</span>}
                                        {dim.name}
                                    </td>
                                    {vendors.map((v, j) => (
                                        <td key={j} style={{
                                            textAlign: 'center', padding: '8px',
                                            color: dim.results[v] ? '#00ff88' : '#3a3a4a'
                                        }}>
                                            {dim.results[v] ? '✅' : '—'}
                                        </td>
                                    ))}
                                    <td style={{
                                        textAlign: 'center', padding: '8px 12px',
                                        color: '#00ff88', fontSize: '12px', fontWeight: 500
                                    }}>
                                        {winner || detail?.winner || '—'}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* Summary */}
            {scorecard.summary && (
                <div style={{ fontSize: '13px', color: '#8a8a9a', marginBottom: '16px' }}>
                    {scorecard.summary}
                </div>
            )}

            {/* Dimension Breakdown */}
            {dimensions.length > 0 && (
                <div>
                    <SectionHeader icon="📋" title="DIMENSION BREAKDOWN" />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {dimensions.map((dim, i) => (
                            <div key={i} style={{
                                background: '#12121a',
                                border: '1px solid #1f1f2e',
                                borderLeft: dim.isPriority ? '3px solid #ffaa00' : '3px solid #00d4ff',
                                borderRadius: '6px',
                                padding: '10px 12px'
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                                    {dim.isPriority && <span style={{ fontSize: '14px' }}>⭐</span>}
                                    <span style={{ color: '#ffffff', fontSize: '14px', fontWeight: 600 }}>{dim.name}</span>
                                    <span style={{
                                        background: 'rgba(0, 255, 136, 0.1)', color: '#00ff88',
                                        padding: '1px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600
                                    }}>
                                        {dim.winner}
                                    </span>
                                </div>
                                {dim.why && (
                                    <div style={{ color: '#8a8a9a', fontSize: '13px', lineHeight: '1.4' }}>
                                        {dim.why}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
