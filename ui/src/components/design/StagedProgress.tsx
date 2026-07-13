/**
 * Wizard run-step staged progress list, per AdversarialCI.dc.html.
 * Each stage renders as a row: circle-dot / label + sub / status text.
 *   - done: green checkmark
 *   - active: cyan pulsing dot
 *   - queued: muted number
 */
export interface Stage {
    label: string;
    sub: string;
}

export default function StagedProgress({
    stages,
    activeIdx,
    allComplete = false,
}: {
    stages: Stage[];
    activeIdx: number;
    allComplete?: boolean;
}) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {stages.map((s, i) => {
                const done = i < activeIdx || allComplete;
                const active = i === activeIdx && !allComplete;
                const dotBg = done
                    ? 'var(--success)'
                    : active
                        ? 'var(--accent)'
                        : 'var(--line-2)';
                const textColor = done
                    ? 'var(--success)'
                    : active
                        ? 'var(--accent)'
                        : 'oklch(0.56 0.006 260)';
                const bg = active ? 'var(--accent-8)' : 'var(--surface-1)';
                const status = done ? 'done' : active ? 'running…' : 'queued';
                return (
                    <div key={s.label} style={{
                        display: 'flex', alignItems: 'center', gap: 14,
                        padding: '14px 16px', borderRadius: 12, background: bg,
                    }}>
                        <div style={{
                            width: 28, height: 28, borderRadius: '50%', background: dotBg,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 13, color: 'var(--bg)', fontWeight: 700, flexShrink: 0,
                            animation: active ? 'acp-pulse 1.2s ease-in-out infinite' : undefined,
                        }}>
                            {done ? '✓' : active ? '' : String(i + 1)}
                        </div>
                        <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 14, fontWeight: 700, color: textColor }}>{s.label}</div>
                            <div style={{ fontSize: 12, color: 'oklch(0.56 0.006 260)', marginTop: 2 }}>{s.sub}</div>
                        </div>
                        <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: textColor }}>{status}</div>
                    </div>
                );
            })}
        </div>
    );
}
