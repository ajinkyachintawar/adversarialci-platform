/**
 * Pill-button filter row used in Vendor Registry and History
 * per AdversarialCI.dc.html. Each option is a pill; the active one
 * fills with a translucent accent.
 */
export interface PillOption<T extends string> {
    key: T;
    label: string;
}

export default function PillFilter<T extends string>({
    options,
    value,
    onChange,
}: {
    options: PillOption<T>[];
    value: T;
    onChange: (key: T) => void;
}) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {options.map(o => {
                const active = o.key === value;
                return (
                    <button
                        key={o.key}
                        onClick={() => onChange(o.key)}
                        style={{
                            background: active ? 'var(--accent-12)' : 'transparent',
                            color: active ? 'var(--accent)' : 'var(--text-2)',
                            border: `1px solid ${active ? 'var(--accent-35)' : 'var(--line-2)'}`,
                            padding: '9px 16px',
                            borderRadius: 8,
                            fontFamily: 'inherit',
                            fontSize: 13,
                            fontWeight: 600,
                            cursor: 'pointer',
                        }}
                    >
                        {o.label}
                    </button>
                );
            })}
        </div>
    );
}
