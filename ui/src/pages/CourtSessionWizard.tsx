import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { StagedProgress } from '../components/design';
import type { Stage } from '../components/design';
import { useAllVendors } from '../hooks/useApi';
import { authFetch } from '../lib/api';
import { supabase } from '../lib/supabase';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

type Mode = 'buyer' | 'seller' | 'analyst' | 'sourcing';
type Vertical = 'database' | 'cloud' | 'crm';

interface EnrichedVendor {
    name: string;
    vertical: string;
    atlas: { research_count: number; status: string; sources?: Record<string, number> } | null;
}

interface PlaintiffQuestion {
    key: string;
    prompt: string;
    example?: string;
    required?: boolean;
}

interface VerticalConfig { plaintiff_questions?: PlaintiffQuestion[]; }

const VERTICAL_META: Record<Vertical, { icon: string; label: string }> = {
    database: { icon: '▤', label: 'Database' },
    cloud:    { icon: '◇', label: 'Cloud' },
    crm:      { icon: '◈', label: 'CRM' },
};

const MODES: { key: Mode; label: string; desc: string }[] = [
    { key: 'buyer',    label: 'Buyer',    desc: 'Which vendor should I pick?' },
    { key: 'seller',   label: 'Seller',   desc: 'How do I position vs. a competitor?' },
    { key: 'analyst',  label: 'Analyst',  desc: 'Neutral comparison, no declared winner.' },
    { key: 'sourcing', label: 'Sourcing', desc: 'Freshness check only, no court session.' },
];

const RUN_STAGES: Stage[] = [
    { label: 'Researching vendors', sub: 'Pricing, GitHub activity, blog posts, forums' },
    { label: 'Building the case',   sub: 'Adversarial argument for each vendor' },
    { label: 'Scoring & judging',   sub: 'Weighing evidence against your priorities' },
    { label: 'Writing report',      sub: 'Assembling verdict and comparison tables' },
];

/** Map a raw SSE log line to a stage index. */
function lineToStage(line: string): number {
    if (/report|writing|drafting|assembling|winner|section/i.test(line))              return 3;
    if (/judg|verdict|score|weigh|deliberat|confidence/i.test(line))                  return 2;
    if (/argument|advocate|counsel|round|adversar|challenge/i.test(line))             return 1;
    return 0;
}

const LOG_COLORS = ['var(--accent)', 'var(--text-3)', 'var(--warn)'];

export default function CourtSessionWizard() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    const [step, setStep] = useState(0);
    const [vertical, setVertical] = useState<Vertical>('database');
    const [mode, setMode] = useState<Mode>(() => {
        const m = searchParams.get('mode');
        return (m === 'buyer' || m === 'seller' || m === 'analyst' || m === 'sourcing') ? m : 'buyer';
    });
    const [briefMode, setBriefMode] = useState(false);
    const [briefText, setBriefText] = useState('');

    const [selectedIds, setSelectedIds] = useState<string[]>([]);
    const [profileAnswers, setProfileAnswers] = useState<Record<string, string>>({});

    const [sessionId, setSessionId] = useState('');
    const [runStage, setRunStage] = useState(0);
    const [runLog, setRunLog] = useState<{ text: string; color: string }[]>([]);
    const [runComplete, setRunComplete] = useState(false);
    const streamAbort = useRef<AbortController | null>(null);

    /* ─── Data ───────────────────────────────────── */

    const { data: verticalConfig } = useQuery<VerticalConfig>({
        queryKey: ['vertical-config', vertical],
        queryFn: () => authFetch(`/api/verticals/${vertical}`).then(r => r.json()),
    });

    const { data: vendorData } = useAllVendors();
    const verticalVendors: EnrichedVendor[] = useMemo(() => {
        if (!vendorData) return [];
        return (vendorData[vertical] || []) as EnrichedVendor[];
    }, [vendorData, vertical]);

    /* ─── Derived ────────────────────────────────── */

    const stepLabels = [
        'Step 1 of 4 — vertical & mode',
        'Step 2 of 4 — pick vendors',
        mode === 'sourcing' ? 'Step 3 of 4 — running refresh' : 'Step 3 of 4 — your profile',
        'Step 4 of 4 — running evaluation',
    ];

    const questions: PlaintiffQuestion[] = verticalConfig?.plaintiff_questions ?? [];
    const requiredQs = questions.filter(q => q.required);
    const profileComplete = requiredQs.every(q => (profileAnswers[q.key] || '').trim().length > 0);

    const step1CanContinue = selectedIds.length >= 2;

    /* ─── Actions ────────────────────────────────── */

    const toggleVendor = (id: string) => {
        setSelectedIds(prev => {
            if (prev.includes(id)) return prev.filter(x => x !== id);
            if (prev.length >= 4) return prev;
            return [...prev, id];
        });
    };

    const advance = () => {
        if (step === 1 && mode === 'sourcing') { setStep(3); startRun(); return; }
        if (step === 2) { startRun(); return; }
        setStep(s => Math.min(s + 1, 3));
    };

    const goBack = () => setStep(s => {
        if (s === 3 && mode === 'sourcing') return 1;
        return Math.max(s - 1, 0);
    });

    const startRun = () => {
        setStep(3);
        setRunStage(0);
        setRunLog([]);
        setRunComplete(false);

        const primary = selectedIds[0] || '';
        const competitors = selectedIds.slice(1);

        const plaintiff: Record<string, string> = { mode, ...profileAnswers };
        if (briefMode && briefText.trim()) plaintiff.brief = briefText.trim();

        const payload = { vertical, mode, primary, competitors, plaintiff };

        authFetch(`/api/evaluate`, {
            method: 'POST',
            body: JSON.stringify(payload),
        }).then(r => r.json()).then(data => {
            if (!data.session_id) throw new Error(data.detail || 'no session_id');
            setSessionId(data.session_id);
            openStream(data.session_id);
        }).catch(err => {
            setRunLog(l => [...l, { text: `✗ error: ${err.message}`, color: 'var(--danger)' }]);
        });
    };

    const openStream = async (sid: string) => {
        streamAbort.current?.abort();
        const ctrl = new AbortController();
        streamAbort.current = ctrl;

        // SSE middleware reads token from ?token= (EventSource-compatible pattern).
        const { data: { session } } = await supabase.auth.getSession();
        const tokenQ = session ? `?token=${encodeURIComponent(session.access_token)}` : '';

        fetch(`${API_BASE_URL}/api/stream/${sid}${tokenQ}`, { signal: ctrl.signal })
            .then(async response => {
                const reader = response.body?.getReader();
                const decoder = new TextDecoder();
                if (!reader) return;

                let buffer = '';
                let stage = 0;
                let logIdx = 0;

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';
                    for (const line of lines) {
                        if (!line.startsWith('data:')) continue;
                        const data = line.substring(5).trim();
                        if (!data || data === 'keep-alive') continue;

                        if (data.startsWith('__REPORT_READY__:')) {
                            const reportId = data.substring('__REPORT_READY__:'.length);
                            setRunStage(RUN_STAGES.length);
                            setRunComplete(true);
                            setTimeout(() => navigate(`/report/${reportId}`), 1200);
                            return;
                        }
                        if (data === '__DONE__') return;
                        if (data.startsWith('ERROR:')) {
                            setRunLog(l => [...l, { text: data, color: 'var(--danger)' }]);
                            continue;
                        }

                        const newStage = lineToStage(data);
                        if (newStage > stage) { stage = newStage; setRunStage(stage); }

                        const color = LOG_COLORS[logIdx % LOG_COLORS.length];
                        logIdx += 1;
                        setRunLog(l => [...l, { text: data, color }]);
                    }
                }
            })
            .catch(err => {
                if (err.name === 'AbortError') return;
                setRunLog(l => [...l, { text: `✗ stream error: ${err.message}`, color: 'var(--danger)' }]);
            });
    };

    useEffect(() => () => streamAbort.current?.abort(), []);

    /* ─── Render ─────────────────────────────────── */

    return (
        <div style={{ padding: '36px 44px', maxWidth: 900 }} className="animate-fade-in">
            <h1 style={{
                fontSize: 26, fontWeight: 800, margin: '0 0 4px', letterSpacing: '-0.02em',
            }}>New evaluation</h1>
            <p style={{ fontSize: 14, color: 'var(--text-3)', margin: '0 0 28px' }}>{stepLabels[step]}</p>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 32 }}>
                {[0, 1, 2, 3].map(i => (
                    <div key={i} style={{
                        flex: 1, height: 4, borderRadius: 4,
                        background: i <= step ? 'var(--accent)' : 'var(--line)',
                    }} />
                ))}
            </div>

            {step === 0 && (
                <Step0
                    vertical={vertical}
                    setVertical={setVertical}
                    mode={mode}
                    setMode={setMode}
                    briefMode={briefMode}
                    setBriefMode={setBriefMode}
                    briefText={briefText}
                    setBriefText={setBriefText}
                    vendorCounts={{
                        database: (vendorData?.database || []).length,
                        cloud:    (vendorData?.cloud    || []).length,
                        crm:      (vendorData?.crm      || []).length,
                    }}
                    onNext={advance}
                />
            )}

            {step === 1 && (
                <Step1
                    mode={mode}
                    vendors={verticalVendors}
                    selectedIds={selectedIds}
                    onToggle={toggleVendor}
                    canContinue={step1CanContinue}
                    onNext={advance}
                    onBack={goBack}
                />
            )}

            {step === 2 && (
                <Step2
                    questions={questions}
                    answers={profileAnswers}
                    onChange={(key, val) => setProfileAnswers(p => ({ ...p, [key]: val }))}
                    canContinue={profileComplete}
                    onNext={advance}
                    onBack={goBack}
                />
            )}

            {step === 3 && (
                <Step3
                    activeStage={runStage}
                    complete={runComplete}
                    log={runLog}
                    initializing={!sessionId}
                />
            )}
        </div>
    );
}

/* ─── Step 0 ───────────────────────────────────── */

function Step0({
    vertical, setVertical, mode, setMode,
    briefMode, setBriefMode, briefText, setBriefText,
    vendorCounts, onNext,
}: {
    vertical: Vertical;
    setVertical: (v: Vertical) => void;
    mode: Mode;
    setMode: (m: Mode) => void;
    briefMode: boolean;
    setBriefMode: (b: boolean) => void;
    briefText: string;
    setBriefText: (v: string) => void;
    vendorCounts: Record<Vertical, number>;
    onNext: () => void;
}) {
    return (
        <>
            <h3 style={sectionHeadingStyle}>Vertical</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 30 }}>
                {(Object.entries(VERTICAL_META) as [Vertical, { icon: string; label: string }][]).map(([key, meta]) => {
                    const active = vertical === key;
                    return (
                        <div
                            key={key}
                            onClick={() => setVertical(key)}
                            style={{
                                background: active ? 'var(--accent-10)' : 'var(--surface-1)',
                                border: `1px solid ${active ? 'oklch(0.66 0.09 205 / 0.4)' : 'var(--line)'}`,
                                borderRadius: 14, padding: 18, cursor: 'pointer',
                            }}
                        >
                            <div style={{ fontSize: 20, marginBottom: 8 }}>{meta.icon}</div>
                            <div style={{ fontSize: 15, fontWeight: 700 }}>{meta.label}</div>
                            <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>
                                {vendorCounts[key]} vendors tracked
                            </div>
                        </div>
                    );
                })}
            </div>

            <h3 style={sectionHeadingStyle}>Mode</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 30 }}>
                {MODES.map(m => {
                    const active = mode === m.key;
                    return (
                        <div
                            key={m.key}
                            onClick={() => setMode(m.key)}
                            style={{
                                background: active ? 'var(--accent-10)' : 'var(--surface-1)',
                                border: `1px solid ${active ? 'oklch(0.66 0.09 205 / 0.4)' : 'var(--line)'}`,
                                borderRadius: 14, padding: 16, cursor: 'pointer',
                            }}
                        >
                            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{m.label}</div>
                            <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.4 }}>{m.desc}</div>
                        </div>
                    );
                })}
            </div>

            <div style={{
                display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24,
                background: 'var(--surface-1)', border: '1px solid var(--line)',
                borderRadius: 12, padding: '14px 16px',
            }}>
                <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: 'var(--accent)',
                }}>&gt;_</span>
                <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>Prefer to just describe your situation?</div>
                    <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                        Skip the structured form — write a free-text brief and we'll parse it.
                    </div>
                </div>
                <button
                    onClick={() => setBriefMode(!briefMode)}
                    style={{
                        background: briefMode ? 'var(--accent-25)' : 'transparent',
                        border: '1px solid var(--accent-30)',
                        color: 'var(--accent)',
                        padding: '8px 14px', borderRadius: 8,
                        fontFamily: 'inherit', fontSize: 12, fontWeight: 700, cursor: 'pointer',
                        flexShrink: 0,
                    }}
                >
                    {briefMode ? 'Use structured form' : 'Write a brief instead'}
                </button>
            </div>

            {briefMode && (
                <textarea
                    value={briefText}
                    onChange={e => setBriefText(e.target.value)}
                    placeholder="e.g. We're a 40-person fintech startup on AWS, need a Postgres-compatible database that scales to 10M rows without ops overhead, budget-conscious…"
                    style={{
                        width: '100%', boxSizing: 'border-box', height: 120,
                        background: 'oklch(1 0 0 / 0.04)', border: '1px solid var(--line-2)',
                        borderRadius: 12, padding: 14, color: 'var(--text)',
                        fontFamily: 'var(--font-mono)', fontSize: 13,
                        resize: 'vertical', outline: 'none', marginBottom: 24,
                    }}
                />
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button onClick={onNext} style={primaryButtonStyle}>Continue →</button>
            </div>
        </>
    );
}

/* ─── Step 1 ───────────────────────────────────── */

function Step1({
    mode, vendors, selectedIds, onToggle, canContinue, onNext, onBack,
}: {
    mode: Mode;
    vendors: EnrichedVendor[];
    selectedIds: string[];
    onToggle: (id: string) => void;
    canContinue: boolean;
    onNext: () => void;
    onBack: () => void;
}) {
    const hint = mode === 'seller'
        ? 'Pick your company first, then 1-3 competitors.'
        : 'Pick 2-4 vendors to compare.';

    return (
        <>
            <p style={{ fontSize: 13, color: 'var(--text-3)', margin: '0 0 16px' }}>{hint}</p>

            {vendors.length === 0 ? (
                <div style={{
                    background: 'var(--surface-1)', border: '1px solid var(--line)',
                    borderRadius: 12, padding: '32px 20px', textAlign: 'center',
                    color: 'var(--text-3)', fontSize: 13, marginBottom: 28,
                }}>Loading vendors…</div>
            ) : (
                <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: 12, marginBottom: 28,
                }}>
                    {vendors.map(v => {
                        const checked = selectedIds.includes(v.name);
                        const docTotal = v.atlas?.research_count ?? 0;
                        const fresh = v.atlas?.status ?? 'new';
                        return (
                            <div
                                key={v.name}
                                onClick={() => onToggle(v.name)}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 12,
                                    background: checked ? 'var(--accent-8)' : 'var(--surface-1)',
                                    border: `1px solid ${checked ? 'var(--accent-35)' : 'var(--line)'}`,
                                    borderRadius: 12, padding: '14px 16px', cursor: 'pointer',
                                }}
                            >
                                <div style={{
                                    width: 20, height: 20, borderRadius: 6,
                                    border: `2px solid ${checked ? 'var(--accent)' : 'oklch(1 0 0 / 0.2)'}`,
                                    background: checked ? 'var(--accent)' : 'transparent',
                                    flexShrink: 0,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: 12, color: 'var(--bg)', fontWeight: 700,
                                }}>{checked ? '✓' : ''}</div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{
                                        fontSize: 14, fontWeight: 700,
                                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                    }}>{v.name}</div>
                                    <div style={{ fontSize: 11, color: 'var(--text-3)' }}>
                                        {docTotal} docs · {fresh}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            <NavRow onBack={onBack} onNext={onNext} nextEnabled={canContinue} />
        </>
    );
}

/* ─── Step 2 ───────────────────────────────────── */

function Step2({
    questions, answers, onChange, canContinue, onNext, onBack,
}: {
    questions: PlaintiffQuestion[];
    answers: Record<string, string>;
    onChange: (key: string, val: string) => void;
    canContinue: boolean;
    onNext: () => void;
    onBack: () => void;
}) {
    return (
        <>
            {questions.length === 0 ? (
                <div style={{
                    background: 'var(--surface-1)', border: '1px solid var(--line)',
                    borderRadius: 12, padding: '32px 20px', textAlign: 'center',
                    color: 'var(--text-3)', fontSize: 13, marginBottom: 24,
                }}>Loading form…</div>
            ) : (
                <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: 16, marginBottom: 24,
                }}>
                    {questions.map(q => (
                        <div key={q.key}>
                            <label style={{
                                fontSize: 12, fontWeight: 600, color: 'var(--text-3)',
                                display: 'block', marginBottom: 6,
                            }}>
                                {q.prompt.replace(/:\s*$/, '')}
                                {q.required && <span style={{ color: 'var(--warn)' }}> *</span>}
                            </label>
                            <input
                                value={answers[q.key] || ''}
                                onChange={e => onChange(q.key, e.target.value)}
                                placeholder={q.example || ''}
                                style={{
                                    width: '100%', boxSizing: 'border-box',
                                    background: 'oklch(1 0 0 / 0.04)', border: '1px solid var(--line-2)',
                                    borderRadius: 9, padding: '11px 13px',
                                    color: 'var(--text)', fontFamily: 'inherit', fontSize: 14,
                                    outline: 'none',
                                }}
                            />
                        </div>
                    ))}
                </div>
            )}

            <NavRow onBack={onBack} onNext={onNext} nextEnabled={canContinue} nextLabel="Run evaluation →" />
        </>
    );
}

/* ─── Step 3 ───────────────────────────────────── */

function Step3({
    activeStage, complete, log, initializing,
}: {
    activeStage: number;
    complete: boolean;
    log: { text: string; color: string }[];
    initializing: boolean;
}) {
    return (
        <>
            <div style={{ marginBottom: 24 }}>
                <StagedProgress stages={RUN_STAGES} activeIdx={activeStage} allComplete={complete} />
            </div>
            {initializing && log.length === 0 ? (
                <div style={{
                    background: 'oklch(0 0 0 / 0.35)', border: '1px solid var(--line)',
                    borderRadius: 12, padding: 16, minHeight: 60,
                    fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-3)',
                }}>Initializing…</div>
            ) : (
                <div style={{
                    background: 'oklch(0 0 0 / 0.35)', border: '1px solid var(--line)',
                    borderRadius: 12, padding: 16, height: 220, overflowY: 'auto',
                    fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.7,
                }}>
                    {log.map((l, i) => (
                        <div key={i} style={{ color: l.color }}>{l.text}</div>
                    ))}
                </div>
            )}
        </>
    );
}

/* ─── Shared bits ──────────────────────────────── */

function NavRow({
    onBack, onNext, nextEnabled, nextLabel = 'Continue →',
}: {
    onBack: () => void;
    onNext: () => void;
    nextEnabled: boolean;
    nextLabel?: string;
}) {
    return (
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <button
                onClick={onBack}
                style={{
                    background: 'none', border: '1px solid oklch(1 0 0 / 0.12)',
                    color: 'var(--text)',
                    padding: '12px 22px', borderRadius: 9,
                    fontFamily: 'inherit', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                }}
            >← Back</button>
            <button
                onClick={onNext}
                disabled={!nextEnabled}
                style={{
                    background: nextEnabled ? 'var(--accent)' : 'oklch(1 0 0 / 0.1)',
                    color: 'var(--bg)', border: 'none',
                    padding: '12px 24px', borderRadius: 9,
                    fontFamily: 'inherit', fontSize: 14, fontWeight: 700,
                    cursor: nextEnabled ? 'pointer' : 'not-allowed',
                    opacity: nextEnabled ? 1 : 0.6,
                }}
            >{nextLabel}</button>
        </div>
    );
}

const sectionHeadingStyle: React.CSSProperties = {
    fontSize: 14, fontWeight: 700, color: 'var(--text-3)',
    textTransform: 'uppercase', letterSpacing: '0.04em', margin: '0 0 12px',
};

const primaryButtonStyle: React.CSSProperties = {
    background: 'var(--accent)', color: 'var(--bg)', border: 'none',
    padding: '12px 24px', borderRadius: 9,
    fontFamily: 'inherit', fontSize: 14, fontWeight: 700, cursor: 'pointer',
};
