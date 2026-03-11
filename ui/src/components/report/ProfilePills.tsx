import type { ProfileData } from '../../lib/reportParser';

interface ProfilePillsProps {
    profile: ProfileData;
    label?: string;
}

export function ProfilePills({ profile, label = 'Your Requirements' }: ProfilePillsProps) {
    const pills = [
        { label: 'Company', value: profile.company },
        { label: 'Team', value: profile.team },
        { label: 'Budget', value: profile.budget },
        { label: 'Use Case', value: profile.useCase },
        { label: 'Scale', value: profile.scale },
    ].filter(p => p.value && p.value !== 'N/A');

    return (
        <div style={{
            background: '#12121a',
            border: '1px solid #2a2a3a',
            borderRadius: '8px',
            padding: '16px',
            marginBottom: '16px'
        }}>
            <div style={{
                fontSize: '11px',
                color: '#8a8a9a',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                marginBottom: '10px'
            }}>
                {label}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: profile.priority ? '12px' : 0 }}>
                {pills.map((p, i) => (
                    <span key={i} style={{
                        background: '#1a1a24',
                        border: '1px solid #2a2a3a',
                        borderRadius: '16px',
                        padding: '4px 12px',
                        fontSize: '13px',
                        color: '#ffffff',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px'
                    }}>
                        <span style={{ color: '#8a8a9a', fontSize: '11px' }}>{p.label}:</span>
                        {p.value}
                    </span>
                ))}
            </div>
            {profile.priority && (
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '13px',
                    color: '#ffaa00'
                }}>
                    <span>⭐</span>
                    <span>Priority: <strong style={{ color: '#ffffff' }}>{profile.priority}</strong></span>
                </div>
            )}
        </div>
    );
}
