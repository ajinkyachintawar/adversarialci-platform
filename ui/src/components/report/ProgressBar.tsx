interface ProgressBarProps {
    value: number;
    max: number;
    label?: string;
    color?: 'cyan' | 'green' | 'yellow' | 'red';
}

export function ProgressBar({ value, max, label, color = 'cyan' }: ProgressBarProps) {
    const percentage = max > 0 ? (value / max) * 100 : 0;

    const colorMap = {
        cyan: '#00d4ff',
        green: '#00ff88',
        yellow: '#ffaa00',
        red: '#ff4466'
    };

    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', margin: '4px 0' }}>
            {label && (
                <span style={{ minWidth: '120px', color: '#ffffff', fontSize: '14px' }}>
                    {label}
                </span>
            )}
            <div style={{
                flex: 1,
                height: '8px',
                background: '#1a1a24',
                borderRadius: '4px',
                overflow: 'hidden'
            }}>
                <div style={{
                    width: `${percentage}%`,
                    height: '100%',
                    background: colorMap[color],
                    borderRadius: '4px',
                    transition: 'width 0.3s ease'
                }} />
            </div>
            <span style={{ minWidth: '40px', textAlign: 'right', color: '#8a8a9a', fontSize: '13px' }}>
                {value}/{max}
            </span>
        </div>
    );
}
