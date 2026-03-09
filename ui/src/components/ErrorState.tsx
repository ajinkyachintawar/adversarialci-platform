import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 'var(--sp-12) var(--sp-6)',
            gap: 'var(--sp-4)',
            textAlign: 'center',
        }}>
            <AlertTriangle size={36} style={{ color: 'var(--accent-red)', opacity: 0.8 }} />
            <div>
                <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)', maxWidth: 360 }}>{message}</p>
            </div>
            {onRetry && (
                <button className="btn btn-secondary" onClick={onRetry} style={{ marginTop: 'var(--sp-2)' }}>
                    <RefreshCw size={14} /> Retry
                </button>
            )}
        </div>
    );
}
