/**
 * Mono terminal-style log tail with a horizontal scanning-line effect,
 * per AdversarialCI.dc.html — used by the vendor refresh SSE UI and
 * the wizard run-step log window.
 */
export default function LogTail({
    lines,
    height = 200,
    variant = 'wizard',
}: {
    lines: string[];
    height?: number;
    variant?: 'wizard' | 'inline';
}) {
    const scanning = variant === 'inline'; // inline (vendor refresh) shows the scanning line

    return (
        <div style={{
            background: scanning ? 'oklch(0 0 0 / 0.3)' : 'oklch(0 0 0 / 0.35)',
            border: scanning
                ? '1px solid var(--accent-25)'
                : '1px solid var(--line)',
            borderRadius: scanning ? 10 : 12,
            padding: scanning ? 14 : 16,
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            lineHeight: 1.7,
            color: scanning ? 'var(--accent)' : undefined,
            height: scanning ? undefined : height,
            overflowY: 'auto',
            position: 'relative',
        }}>
            {scanning && (
                <div style={{
                    position: 'absolute', top: 0, left: 0, width: '40%', height: 2,
                    background: 'linear-gradient(90deg, transparent, var(--accent), transparent)',
                    animation: 'acp-scan 1.2s linear infinite',
                }} />
            )}
            {lines.map((l, i) => (
                <div key={i} style={{ padding: '2px 0', opacity: 0.9 }}>{l}</div>
            ))}
        </div>
    );
}
