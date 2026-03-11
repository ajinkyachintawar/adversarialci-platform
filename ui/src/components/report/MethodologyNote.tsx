import type { MethodologyStep } from '../../lib/reportParser';

interface MethodologyNoteProps {
    steps: MethodologyStep[];
}

export function MethodologyNote({ steps }: MethodologyNoteProps) {
    return (
        <div style={{
            background: '#12121a',
            border: '1px solid #1f1f2e',
            borderRadius: '8px',
            padding: '14px 16px'
        }}>
            <div style={{
                display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px'
            }}>
                <span style={{ fontSize: '14px' }}>📝</span>
                <span style={{
                    fontSize: '11px', fontWeight: 700, color: '#8a8a9a',
                    textTransform: 'uppercase', letterSpacing: '0.5px'
                }}>
                    Methodology
                </span>
            </div>
            {steps.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {steps.map((step, i) => (
                        <div key={i} style={{ fontSize: '12px', color: '#6a6a7a', lineHeight: '1.5' }}>
                            <span style={{ color: '#8a8a9a', fontWeight: 600 }}>{i + 1}. {step.name}</span>
                            {step.description && (
                                <span style={{ color: '#5a5a6a' }}> — {step.description}</span>
                            )}
                        </div>
                    ))}
                </div>
            ) : (
                <p style={{ fontSize: '12px', color: '#5a5a6a', margin: 0, lineHeight: '1.5' }}>
                    This analysis is based on publicly available data, pricing pages,
                    documentation, GitHub activity, and community sentiment.
                    Each dimension was evaluated independently.
                </p>
            )}
        </div>
    );
}
