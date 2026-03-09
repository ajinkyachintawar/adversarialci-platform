interface BattlecardHeaderProps {
    winProbability: number;
    isFavorite: boolean;
    dimensionsWon: string;
}

export function BattlecardHeader({ winProbability, isFavorite, dimensionsWon }: BattlecardHeaderProps) {
    return (
        <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 2fr 1fr',
            gap: '24px',
            alignItems: 'center',
            padding: '24px',
            background: isFavorite
                ? 'linear-gradient(135deg, rgba(0, 255, 136, 0.1) 0%, rgba(0, 212, 255, 0.1) 100%)'
                : 'linear-gradient(135deg, rgba(255, 170, 0, 0.1) 0%, rgba(255, 68, 102, 0.1) 100%)',
            border: `1px solid ${isFavorite ? 'rgba(0, 255, 136, 0.3)' : 'rgba(255, 170, 0, 0.3)'}`,
            borderRadius: '12px',
            marginBottom: '24px'
        }}>
            <div style={{ textAlign: 'center' }}>
                <div style={{
                    fontSize: '48px',
                    fontWeight: 700,
                    color: isFavorite ? '#00ff88' : '#ffaa00'
                }}>
                    {winProbability}%
                </div>
                <div style={{ fontSize: '12px', color: '#8a8a9a' }}>Win Probability</div>
            </div>

            <div style={{
                textAlign: 'center',
                padding: '16px',
                background: isFavorite ? 'rgba(0, 255, 136, 0.15)' : 'rgba(255, 170, 0, 0.15)',
                borderRadius: '8px'
            }}>
                <div style={{
                    fontSize: '16px',
                    fontWeight: 600,
                    color: isFavorite ? '#00ff88' : '#ffaa00'
                }}>
                    {isFavorite ? "✅ YOU'RE THE FAVORITE" : "⚠️ YOU'RE THE UNDERDOG"}
                </div>
                <div style={{ fontSize: '13px', color: '#8a8a9a', marginTop: '4px' }}>
                    {isFavorite ? "Protect your position" : "Time to differentiate"}
                </div>
            </div>

            <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '14px', color: '#ffffff' }}>{dimensionsWon}</div>
                <div style={{ fontSize: '12px', color: '#8a8a9a' }}>Dimensions Won</div>
            </div>
        </div>
    );
}
