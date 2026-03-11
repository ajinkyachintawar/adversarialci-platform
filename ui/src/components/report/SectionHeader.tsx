interface SectionHeaderProps {
    icon: string;
    title: string;
    color?: string;
}

export function SectionHeader({ icon, title, color = '#00d4ff' }: SectionHeaderProps) {
    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '12px'
        }}>
            <span style={{ fontSize: '16px' }}>{icon}</span>
            <h3 style={{
                margin: 0,
                color,
                fontSize: '13px',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
            }}>
                {title}
            </h3>
        </div>
    );
}
