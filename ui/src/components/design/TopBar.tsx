import { useNavigate } from 'react-router-dom';
import LogoTile from './LogoTile';

/**
 * Public-page top nav, matching AdversarialCI.dc.html Landing/About headers.
 * - variant="landing": Product / Verticals / About / Sign in
 * - variant="about":   Home / Sign in
 * Anchor links use scroll-to-hash on the landing page only.
 */
export default function TopBar({ variant }: { variant: 'landing' | 'about' }) {
    const navigate = useNavigate();

    const linkStyle: React.CSSProperties = {
        color: 'var(--text-3)',
        fontSize: 14,
        textDecoration: 'none',
        cursor: 'pointer',
    };

    return (
        <header style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '24px 48px', maxWidth: 1280, margin: '0 auto', width: '100%',
            boxSizing: 'border-box',
        }}>
            <div
                style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}
                onClick={() => navigate('/')}
            >
                <LogoTile size={32} />
                <span style={{ fontWeight: 700, fontSize: 18, letterSpacing: '-0.02em' }}>AdversarialCI</span>
            </div>

            <nav style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
                {variant === 'landing' ? (
                    <>
                        <a href="#landing-features" style={linkStyle}>Product</a>
                        <a href="#landing-stats" style={linkStyle}>Verticals</a>
                        <span onClick={() => navigate('/about')} style={linkStyle}>About</span>
                    </>
                ) : (
                    <span onClick={() => navigate('/')} style={linkStyle}>Home</span>
                )}
                <button
                    onClick={() => navigate('/login')}
                    style={{
                        background: 'none',
                        border: '1px solid var(--line-strong)',
                        color: 'var(--text)',
                        padding: '9px 18px',
                        borderRadius: 8,
                        fontFamily: 'inherit',
                        fontSize: 14,
                        fontWeight: 600,
                        cursor: 'pointer',
                    }}
                >
                    Sign in
                </button>
            </nav>
        </header>
    );
}
