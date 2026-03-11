import type { AnalystSummary } from '../../lib/reportParser';
import { ProgressBar } from './ProgressBar';

interface AnalystHeaderProps {
    summary: AnalystSummary;
    vertical: string;
}

export function AnalystHeader({ summary, vertical }: AnalystHeaderProps) {
    return (
        <div style={{
            background: 'linear-gradient(135deg, rgba(0, 212, 255, 0.08) 0%, rgba(170, 102, 255, 0.08) 100%)',
            border: '1px solid rgba(0, 212, 255, 0.2)',
            borderRadius: '12px',
            padding: '24px',
            marginBottom: '16px'
        }}>
            <div style={{
                display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px'
            }}>
                <span style={{ fontSize: '28px' }}>📊</span>
                <div>
                    <div style={{
                        fontSize: '11px', color: '#8a8a9a', textTransform: 'uppercase',
                        letterSpacing: '0.5px'
                    }}>
                        Objective Analysis
                    </div>
                    <h2 style={{ margin: 0, color: '#00d4ff', fontSize: '20px', fontWeight: 700 }}>
                        {vertical || 'Market Analysis'}
                    </h2>
                </div>
            </div>

            {summary.description && (
                <p style={{
                    color: '#8a8a9a', fontSize: '14px', lineHeight: '1.5',
                    margin: '0 0 16px', fontStyle: 'italic'
                }}>
                    {summary.description}
                </p>
            )}

            {summary.dimensionWins.length > 0 && (
                <div>
                    <div style={{
                        fontSize: '11px', color: '#8a8a9a', textTransform: 'uppercase',
                        letterSpacing: '0.5px', marginBottom: '8px'
                    }}>
                        Dimension Wins
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {summary.dimensionWins.map((dw, i) => {
                            const pct = dw.total > 0 ? (dw.wins / dw.total) * 100 : 0;
                            const color = pct >= 50 ? 'green' : pct > 0 ? 'yellow' : 'red';
                            return (
                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                    <span style={{ minWidth: '100px', fontSize: '13px', color: '#ffffff', fontWeight: 500 }}>
                                        {dw.vendor}
                                    </span>
                                    <div style={{ flex: 1 }}>
                                        <ProgressBar value={dw.wins} max={dw.total} color={color} />
                                    </div>
                                    <span style={{ minWidth: '40px', textAlign: 'right', fontSize: '13px', color: '#8a8a9a' }}>
                                        {dw.wins}/{dw.total}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
