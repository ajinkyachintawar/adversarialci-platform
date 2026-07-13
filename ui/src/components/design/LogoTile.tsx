/**
 * Gradient "A" logo tile. Size drives the visual scale.
 * Matches AdversarialCI.dc.html sizes: 28 (sidebar), 32 (top bar), 48 (login hero).
 */
export default function LogoTile({ size = 32 }: { size?: number }) {
    const radius = Math.round(size * 0.22);
    const fontSize = Math.round(size * 0.47);
    return (
        <div style={{
            width: size,
            height: size,
            borderRadius: radius,
            background: 'var(--logo-grad)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            color: 'var(--bg)',
            fontSize,
            flexShrink: 0,
        }}>A</div>
    );
}
