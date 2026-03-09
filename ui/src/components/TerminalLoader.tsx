import { useState, useEffect, useRef } from 'react';

export default function TerminalLoader({ sessionId, onComplete }: { sessionId: string, onComplete: (reportId: string) => void }) {
    const [logs, setLogs] = useState<string[]>(["Connecting to Adversarial CI Engine..."]);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!sessionId) return;

        let pendingReportId = "";

        const eventSource = new EventSource(`http://127.0.0.1:8000/api/stream/${sessionId}`);

        eventSource.onmessage = (event) => {
            const data = event.data;

            if (data.startsWith("__REPORT_READY__:")) {
                pendingReportId = data.split(":")[1];
                setLogs(prev => [...prev, "[SYSTEM] ✅ Deliberation complete. Report generated."]);
                return;
            }

            if (data === "__DONE__") {
                eventSource.close();
                setLogs(prev => [...prev, "[SYSTEM] Session ended."]);
                if (pendingReportId) {
                    setTimeout(() => onComplete(pendingReportId), 1500);
                } else {
                    setLogs(prev => [...prev, "[SYSTEM] ⚠️ No report was generated. Check server logs."]);
                }
                return;
            }

            if (data && data.trim()) {
                setLogs(prev => [...prev, data]);
            }
        };

        eventSource.onerror = (err) => {
            console.error("EventSource failed:", err);
            setLogs(prev => [...prev, "[ERROR] Connection to war room lost."]);
            eventSource.close();
        };

        return () => eventSource.close();
    }, [sessionId, onComplete]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    return (
        <div ref={scrollRef} style={{
            padding: 'var(--sp-4)',
            height: 320,
            overflowY: 'auto',
            background: 'rgba(5, 5, 10, 0.85)',
            border: '1px solid rgba(0, 212, 255, 0.15)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'inset 0 0 20px rgba(0,0,0,0.4)',
            display: 'flex',
            flexDirection: 'column',
        }}>
            {/* Terminal dots */}
            <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-3)' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-red)' }} />
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-yellow)' }} />
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-green)' }} />
            </div>

            {/* Logs */}
            <div className="terminal-text" style={{ color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 'var(--sp-1)' }}>
                {logs.map((log, i) => (
                    <div key={i} className="animate-fade-in" style={{
                        color: log.includes('---') ? 'var(--accent-cyan)' :
                            log.includes('[JUDGE]') ? 'var(--accent-purple)' :
                                log.includes('[ADVOCATES]') ? 'var(--accent-yellow)' :
                                    log.includes('[SYSTEM]') ? 'var(--accent-green)' :
                                        log.includes('[ERROR]') ? 'var(--accent-red)' : 'inherit',
                    }}>
                        <span style={{ color: 'var(--text-muted)', marginRight: 'var(--sp-3)', fontSize: 'var(--text-xs)' }}>
                            {new Date().toISOString().split('T')[1].slice(0, 8)}
                        </span>
                        {log}
                    </div>
                ))}
                <div className="animate-pulse-glow" style={{
                    width: 7, height: 14,
                    background: 'var(--accent-cyan)',
                    marginTop: 'var(--sp-1)',
                    borderRadius: 1,
                }} />
            </div>
        </div>
    );
}
