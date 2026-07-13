import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader } from 'lucide-react';
import { supabase } from '../lib/supabase';
import { LogoTile } from '../components/design';

export default function Login() {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleGoogleLogin = async () => {
        setLoading(true);
        setError('');
        const { error } = await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: { redirectTo: `${window.location.origin}/dashboard` },
        });
        if (error) {
            setError(error.message);
            setLoading(false);
        }
    };

    return (
        <div style={{
            minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
            position: 'relative', background: 'var(--bg)',
        }}>
            <div
                onClick={() => navigate('/')}
                style={{
                    position: 'absolute', top: 32, left: 48,
                    display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer',
                }}
            >
                <LogoTile size={28} />
                <span style={{ fontWeight: 700, fontSize: 16 }}>AdversarialCI</span>
            </div>

            <div style={{
                width: 400,
                background: 'oklch(1 0 0 / 0.035)',
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                border: '1px solid var(--line)',
                borderRadius: 16,
                padding: '44px 40px',
                textAlign: 'center',
                boxShadow: '0 24px 60px -12px oklch(0 0 0 / 0.5)',
            }}>
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
                    <LogoTile size={48} />
                </div>

                <h1 style={{
                    fontSize: 22, fontWeight: 700, margin: '0 0 8px', letterSpacing: '-0.01em',
                }}>
                    Sign in to AdversarialCI
                </h1>
                <p style={{ fontSize: 14, color: 'var(--text-3)', margin: '0 0 32px' }}>
                    Run evaluations, manage vendor intel, and review verdicts.
                </p>

                <button
                    onClick={handleGoogleLogin}
                    disabled={loading}
                    style={{
                        width: '100%',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                        background: 'var(--text)', color: 'var(--bg)', border: 'none',
                        padding: 13, borderRadius: 10, fontFamily: 'inherit',
                        fontSize: 14, fontWeight: 700, cursor: loading ? 'default' : 'pointer',
                        opacity: loading ? 0.7 : 1,
                    }}
                >
                    {loading ? <Loader size={16} className="animate-spin" /> : <GoogleQuadIcon />}
                    Continue with Google
                </button>

                {error && (
                    <p style={{ marginTop: 16, fontSize: 12, color: 'var(--danger)' }}>{error}</p>
                )}

                <p style={{ fontSize: 12, color: 'var(--text-4)', margin: '20px 0 0' }}>
                    Browsing vendor intel &amp; reports doesn't require sign-in.
                </p>
            </div>
        </div>
    );
}

/** 2x2 colored grid Google icon, matching AdversarialCI.dc.html exactly. */
function GoogleQuadIcon() {
    return (
        <span style={{
            width: 16, height: 16, borderRadius: 3,
            display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr',
            overflow: 'hidden', flexShrink: 0,
        }}>
            <span style={{ background: '#4285F4' }} />
            <span style={{ background: '#EA4335' }} />
            <span style={{ background: '#FBBC05' }} />
            <span style={{ background: '#34A853' }} />
        </span>
    );
}
