import { ProgressBar } from './ProgressBar';

interface WinnerCardProps {
    winner: string;
    confidence: number;
    summary?: string;
}

export function WinnerCard({ winner, confidence, summary }: WinnerCardProps) {
    const confidenceColor = confidence >= 75 ? 'green' : confidence >= 50 ? 'yellow' : 'red';

    return (
        <div style={{
            background: 'linear-gradient(135deg, rgba(0, 255, 136, 0.1) 0%, rgba(0, 212, 255, 0.1) 100%)',
            border: '1px solid rgba(0, 255, 136, 0.3)',
            borderRadius: '12px',
            padding: '24px',
            textAlign: 'center',
            marginBottom: '24px'
        }}>
            <div style={{ fontSize: '48px', marginBottom: '8px' }}>🏆</div>
            <div style={{
                fontSize: '12px',
                color: '#8a8a9a',
                textTransform: 'uppercase',
                letterSpacing: '1px',
                marginBottom: '4px'
            }}>
                BEST FIT FOR YOU
            </div>
            <h2 style={{
                fontSize: '32px',
                color: '#00ff88',
                margin: '8px 0 16px',
                fontWeight: 700
            }}>
                {winner}
            </h2>
            <div style={{ maxWidth: '300px', margin: '0 auto 16px' }}>
                <div style={{ fontSize: '12px', color: '#8a8a9a', marginBottom: '8px' }}>
                    CONFIDENCE
                </div>
                <ProgressBar value={confidence} max={100} color={confidenceColor} />
            </div>
            {summary && (
                <p style={{
                    color: '#8a8a9a',
                    fontStyle: 'italic',
                    maxWidth: '600px',
                    margin: '16px auto 0',
                    fontSize: '14px',
                    lineHeight: '1.5'
                }}>
                    "{summary}"
                </p>
            )}
        </div>
    );
}
