import type { TradeoffsData } from '../../lib/reportParser';
import { SectionHeader } from './SectionHeader';

interface TradeoffsSectionProps {
    tradeoffs: TradeoffsData;
}

export function TradeoffsSection({ tradeoffs }: TradeoffsSectionProps) {
    return (
        <div style={{ marginBottom: '16px' }}>
            <SectionHeader icon="⚖️" title="TRADEOFFS YOU'RE MAKING" />
            <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px'
            }}>
                {/* Benefits */}
                <div style={{
                    background: 'rgba(0, 255, 136, 0.04)',
                    border: '1px solid rgba(0, 255, 136, 0.15)',
                    borderRadius: '8px',
                    padding: '14px'
                }}>
                    <div style={{
                        fontSize: '12px', fontWeight: 700, color: '#00ff88',
                        textTransform: 'uppercase', marginBottom: '10px'
                    }}>
                        ✅ By choosing {tradeoffs.chosenVendor}, you get:
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {tradeoffs.benefits.map((b, i) => (
                            <div key={i} style={{
                                display: 'flex', gap: '8px', alignItems: 'flex-start',
                                fontSize: '13px', color: '#e0e0e0', lineHeight: '1.4'
                            }}>
                                <span style={{ color: '#00ff88', flexShrink: 0 }}>✅</span>
                                <span>{b}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Sacrifices */}
                <div style={{
                    background: 'rgba(255, 170, 0, 0.04)',
                    border: '1px solid rgba(255, 170, 0, 0.15)',
                    borderRadius: '8px',
                    padding: '14px'
                }}>
                    <div style={{
                        fontSize: '12px', fontWeight: 700, color: '#ffaa00',
                        textTransform: 'uppercase', marginBottom: '10px'
                    }}>
                        ⚠️ But you may sacrifice:
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {tradeoffs.sacrifices.map((s, i) => (
                            <div key={i} style={{
                                display: 'flex', gap: '8px', alignItems: 'flex-start',
                                fontSize: '13px', color: '#e0e0e0', lineHeight: '1.4'
                            }}>
                                <span style={{ color: '#ffaa00', flexShrink: 0 }}>⚠️</span>
                                <span>{s}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
