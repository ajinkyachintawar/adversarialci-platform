import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Target, User, ServerCog, Cpu, ShieldAlert, ArrowRight, ArrowLeft, Check, BarChart3, Crosshair, Briefcase } from 'lucide-react';
import TerminalLoader from '../components/TerminalLoader';
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

// ─── Step definitions per mode ────────────────────────────────
type StepDef = { key: string; label: string; icon: React.ElementType };

const BUYER_STEPS: StepDef[] = [
    { key: 'SETUP', label: 'Mission', icon: ServerCog },
    { key: 'VENDORS', label: 'Vendors', icon: Target },
    { key: 'PROFILE', label: 'Your Profile', icon: User },
    { key: 'DELIB', label: 'Deliberation', icon: Cpu },
];
const SELLER_STEPS: StepDef[] = [
    { key: 'SETUP', label: 'Mission', icon: ServerCog },
    { key: 'MY_COMPANY', label: 'Your Product', icon: Briefcase },
    { key: 'COMPETITORS', label: 'Competitors', icon: Crosshair },
    { key: 'PROSPECT', label: 'Prospect', icon: User },
    { key: 'DELIB', label: 'Deliberation', icon: Cpu },
];
const ANALYST_STEPS: StepDef[] = [
    { key: 'SETUP', label: 'Mission', icon: ServerCog },
    { key: 'VENDORS', label: 'Vendors', icon: Target },
    { key: 'FOCUS', label: 'Focus Areas', icon: BarChart3 },
    { key: 'DELIB', label: 'Deliberation', icon: Cpu },
];

function getStepsForMode(mode: string): StepDef[] {
    if (mode === 'seller') return SELLER_STEPS;
    if (mode === 'analyst') return ANALYST_STEPS;
    return BUYER_STEPS;
}

const FOCUS_AREAS = ['Cost', 'Performance', 'Scalability', 'Security', 'Ease of Use', 'Ecosystem'];

const MODE_CARDS = [
    { key: 'buyer', label: 'Buyer Evaluation', desc: 'Find the best fit for your requirements.', color: 'var(--accent-cyan)', muted: 'var(--accent-cyan-muted)', icon: Target },
    { key: 'seller', label: 'Seller Battlecard', desc: 'Generate competitive positioning.', color: 'var(--accent-purple)', muted: 'var(--accent-purple-muted)', icon: ShieldAlert },
    { key: 'analyst', label: 'Analyst Comparison', desc: 'Objective market analysis.', color: 'var(--accent-green)', muted: 'var(--accent-green-muted)', icon: BarChart3 },
];

export default function CourtSessionWizard() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    // Core state
    const [stepKey, setStepKey] = useState('SETUP');
    const [vertical, setVertical] = useState('database');
    const [mode, setMode] = useState(searchParams.get('mode') || 'buyer');

    // Vendor list from API
    const [verticalVendors, setVerticalVendors] = useState<string[]>([]);

    // Buyer: multi-select vendors (2-4)
    const [selectedVendors, setSelectedVendors] = useState<string[]>([]);

    // Seller: single primary + multi competitors
    const [myCompany, setMyCompany] = useState('');
    const [sellerCompetitors, setSellerCompetitors] = useState<string[]>([]);

    // Analyst: optional focus areas
    const [focusAreas, setFocusAreas] = useState<string[]>([]);

    // Profile fields (Buyer / Seller prospect)
    const [pCompany, setPCompany] = useState('');
    const [pBudget, setPBudget] = useState('');
    const [pTeamSize, setPTeamSize] = useState('');
    const [pPriority, setPPriority] = useState('cost');
    const [pUseCase, setPUseCase] = useState('');
    const [pScale, setPScale] = useState('');
    const [pCloud, setPCloud] = useState('');

    // Session
    const [session, setSession] = useState('');

    // Read mode from URL on mount
    useEffect(() => {
        const urlMode = searchParams.get('mode');
        if (urlMode && ['buyer', 'seller', 'analyst'].includes(urlMode)) {
            setMode(urlMode);
        }
    }, [searchParams]);

    // Fetch vendors when vertical changes
    useEffect(() => {
        fetch(`${API_BASE_URL}/api/vendors/${vertical}`)
            .then(res => res.json())
            .then(data => {
                setVerticalVendors(Object.keys(data || {}));
                setSelectedVendors([]);
                setMyCompany('');
                setSellerCompetitors([]);
            })
            .catch(e => console.error("Error fetching vendors:", e));
    }, [vertical]);

    // Derived
    const steps = getStepsForMode(mode);
    const stepIndex = steps.findIndex(s => s.key === stepKey);

    // Navigation helpers
    const nextStep = () => {
        const idx = steps.findIndex(s => s.key === stepKey);
        if (idx < steps.length - 1) setStepKey(steps[idx + 1].key);
    };
    const prevStep = () => {
        const idx = steps.findIndex(s => s.key === stepKey);
        if (idx > 0) setStepKey(steps[idx - 1].key);
    };

    // Toggle functions
    const toggleVendor = (v: string) => {
        if (selectedVendors.includes(v)) {
            setSelectedVendors(selectedVendors.filter(x => x !== v));
        } else if (selectedVendors.length < 4) {
            setSelectedVendors([...selectedVendors, v]);
        }
    };
    const toggleSellerComp = (v: string) => {
        if (sellerCompetitors.includes(v)) {
            setSellerCompetitors(sellerCompetitors.filter(x => x !== v));
        } else if (sellerCompetitors.length < 3) {
            setSellerCompetitors([...sellerCompetitors, v]);
        }
    };
    const toggleFocus = (f: string) => {
        if (focusAreas.includes(f)) {
            setFocusAreas(focusAreas.filter(x => x !== f));
        } else {
            setFocusAreas([...focusAreas, f]);
        }
    };

    // Build API payload based on mode
    const buildPayload = () => {
        if (mode === 'buyer') {
            // Buyer: first vendor = primary, rest = competitors
            return {
                vertical,
                mode,
                primary: selectedVendors[0],
                competitors: selectedVendors.slice(1),
                plaintiff: {
                    mode,
                    company_name: pCompany,
                    budget: pBudget,
                    team_size: pTeamSize,
                    priority: pPriority,
                    use_case: pUseCase,
                    scale: pScale,
                    cloud: pCloud,
                },
            };
        } else if (mode === 'seller') {
            return {
                vertical,
                mode,
                primary: myCompany,
                competitors: sellerCompetitors,
                plaintiff: {
                    mode,
                    company_name: pCompany,
                    budget: pBudget,
                    team_size: pTeamSize,
                    priority: pPriority,
                    use_case: pUseCase,
                    scale: pScale,
                    cloud: pCloud,
                },
            };
        } else {
            // Analyst: no profile, optional focus_areas
            return {
                vertical,
                mode,
                primary: selectedVendors[0],
                competitors: selectedVendors.slice(1),
                plaintiff: {
                    mode,
                    company_name: 'Analyst',
                    budget: 'N/A',
                    team_size: 'N/A',
                    priority: 'balanced',
                    use_case: 'market analysis',
                    focus_areas: focusAreas,
                },
            };
        }
    };

    const initiateDeliberation = async () => {
        setStepKey('DELIB');
        try {
            const res = await fetch(`${API_BASE_URL}/api/evaluate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(buildPayload()),
            });
            const data = await res.json();
            if (data.session_id) setSession(data.session_id);
        } catch (e) {
            console.error("Failed to start session:", e);
        }
    };

    const onSimulationComplete = (reportId: string) => {
        navigate(`/report/${reportId}`);
    };

    // ─── Reusable chip component ──────────────────────────────
    const Chip = ({ label, selected, onClick, disabled }: { label: string; selected: boolean; onClick: () => void; disabled?: boolean }) => (
        <button
            onClick={onClick}
            disabled={disabled}
            style={{
                padding: '0.4rem 0.9rem',
                borderRadius: 'var(--radius-full)',
                border: `1px solid ${selected ? 'var(--accent-cyan)' : 'var(--border)'}`,
                background: selected ? 'var(--accent-cyan-muted)' : 'transparent',
                color: selected ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                fontSize: 'var(--text-sm)',
                fontWeight: selected ? 600 : 400,
                transition: 'all 0.2s',
                display: 'flex', alignItems: 'center', gap: 'var(--sp-1)',
                opacity: disabled ? 0.4 : 1,
                cursor: disabled ? 'not-allowed' : 'pointer',
            }}
        >
            {selected && <Check size={12} />}
            {label}
        </button>
    );

    // profile completeness for buyer/seller
    const isProfileComplete = pCompany && pBudget && pTeamSize && pUseCase && pScale;

    return (
        <div className="animate-fade-in">
            <div className="page-header">
                <h1>Court Session</h1>
                <p>Adversarial intelligence resolution pipeline.</p>
            </div>

            {/* ─── Progress Steps ─── */}
            <div style={{
                display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-8)',
                padding: 'var(--sp-4) var(--sp-5)', background: 'var(--bg-surface)', borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border)',
            }}>
                {steps.map((s, i) => {
                    const isComplete = i < stepIndex;
                    const isCurrent = s.key === stepKey;
                    return (
                        <div key={s.key} style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', flex: 1 }}>
                            <div style={{
                                width: 28, height: 28, borderRadius: '50%',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: 'var(--text-xs)', fontWeight: 700, flexShrink: 0,
                                background: isComplete ? 'var(--accent-green)' : isCurrent ? 'var(--accent-cyan)' : 'var(--bg-surface-hover)',
                                color: isComplete || isCurrent ? 'var(--bg-base)' : 'var(--text-muted)',
                                transition: 'all 0.3s ease',
                            }}>
                                {isComplete ? <Check size={14} /> : i + 1}
                            </div>
                            <span style={{
                                fontSize: 'var(--text-sm)', fontWeight: isCurrent ? 600 : 400,
                                color: isCurrent ? 'var(--text-primary)' : isComplete ? 'var(--accent-green)' : 'var(--text-muted)',
                                transition: 'all 0.3s ease', whiteSpace: 'nowrap',
                            }}>
                                {s.label}
                            </span>
                            {i < steps.length - 1 && (
                                <div style={{
                                    flex: 1, height: 1,
                                    background: isComplete ? 'var(--accent-green)' : 'var(--border)',
                                    marginLeft: 'var(--sp-2)', marginRight: 'var(--sp-1)',
                                }} />
                            )}
                        </div>
                    );
                })}
            </div>

            <div className="glass-panel" style={{ padding: 'var(--sp-8)', maxWidth: 820, margin: '0 auto' }}>

                {/* ═══════════════════════════════════════════════════════
                    STEP: SETUP (same for all modes)
                   ═══════════════════════════════════════════════════════ */}
                {stepKey === 'SETUP' && (
                    <div className="animate-fade-in">
                        <h2 style={{ marginBottom: 'var(--sp-6)', display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', fontSize: 'var(--text-lg)' }}>
                            <ServerCog size={20} style={{ color: 'var(--accent-cyan)' }} /> Mission Briefing
                        </h2>

                        <div style={{ display: 'grid', gap: 'var(--sp-6)' }}>
                            <div>
                                <label className="input-label">Select Vertical</label>
                                <select className="input-field" value={vertical} onChange={e => setVertical(e.target.value)}>
                                    <option value="database">Database & Data Platforms</option>
                                    <option value="cloud">Cloud Infrastructure</option>
                                    <option value="crm">CRM & Sales Tools</option>
                                </select>
                            </div>

                            <div>
                                <label className="input-label">Evaluation Mode</label>
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--sp-3)' }}>
                                    {MODE_CARDS.map(m => {
                                        const active = mode === m.key;
                                        return (
                                            <button
                                                key={m.key}
                                                onClick={() => { setMode(m.key); setStepKey('SETUP'); }}
                                                style={{
                                                    padding: 'var(--sp-4)',
                                                    borderRadius: 'var(--radius-md)',
                                                    border: `1px solid ${active ? m.color : 'var(--border)'}`,
                                                    background: active ? m.muted : 'transparent',
                                                    textAlign: 'left',
                                                    transition: 'all 0.2s',
                                                    position: 'relative',
                                                }}
                                            >
                                                {active && (
                                                    <div style={{
                                                        position: 'absolute', top: 8, right: 8, width: 18, height: 18,
                                                        borderRadius: '50%', background: m.color,
                                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                    }}>
                                                        <Check size={11} style={{ color: 'var(--bg-base)' }} />
                                                    </div>
                                                )}
                                                <h3 style={{
                                                    color: active ? m.color : 'var(--text-primary)',
                                                    fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 'var(--sp-1)',
                                                }}>{m.label}</h3>
                                                <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-xs)', lineHeight: 1.5 }}>{m.desc}</p>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--sp-2)' }}>
                                <button className="btn btn-primary" onClick={nextStep}>
                                    {mode === 'seller' ? 'Select Your Product' : 'Select Vendors'} <ArrowRight size={14} />
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* ═══════════════════════════════════════════════════════
                    BUYER: VENDORS (multi-select 2-4 chips)
                   ═══════════════════════════════════════════════════════ */}
                {stepKey === 'VENDORS' && mode === 'buyer' && (
                    <div className="animate-fade-in">
                        <h2 style={{ marginBottom: 'var(--sp-2)', display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', fontSize: 'var(--text-lg)' }}>
                            <Target size={20} style={{ color: 'var(--accent-cyan)' }} /> Which vendors are you evaluating?
                        </h2>
                        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginBottom: 'var(--sp-6)' }}>
                            Select 2–4 vendors to compare side-by-side.
                        </p>

                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-2)', marginBottom: 'var(--sp-6)' }}>
                            {verticalVendors.map(v => (
                                <Chip
                                    key={v}
                                    label={v}
                                    selected={selectedVendors.includes(v)}
                                    onClick={() => toggleVendor(v)}
                                    disabled={!selectedVendors.includes(v) && selectedVendors.length >= 4}
                                />
                            ))}
                        </div>

                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginBottom: 'var(--sp-6)' }}>
                            {selectedVendors.length}/4 selected {selectedVendors.length < 2 && '(min 2)'}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <button className="btn btn-secondary" onClick={prevStep}>
                                <ArrowLeft size={14} /> Back
                            </button>
                            <button className="btn btn-primary" onClick={nextStep} disabled={selectedVendors.length < 2}>
                                Configure Profile <ArrowRight size={14} />
                            </button>
                        </div>
                    </div>
                )}

                {/* ═══════════════════════════════════════════════════════
                    ANALYST: VENDORS (multi-select 2-4 chips)
                   ═══════════════════════════════════════════════════════ */}
                {stepKey === 'VENDORS' && mode === 'analyst' && (
                    <div className="animate-fade-in">
                        <h2 style={{ marginBottom: 'var(--sp-2)', display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', fontSize: 'var(--text-lg)' }}>
                            <BarChart3 size={20} style={{ color: 'var(--accent-green)' }} /> Which vendors to compare?
                        </h2>
                        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginBottom: 'var(--sp-6)' }}>
                            Select 2–4 vendors for objective comparison. No bias, no recommendation.
                        </p>

                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-2)', marginBottom: 'var(--sp-6)' }}>
                            {verticalVendors.map(v => (
                                <Chip
                                    key={v}
                                    label={v}
                                    selected={selectedVendors.includes(v)}
                                    onClick={() => toggleVendor(v)}
                                    disabled={!selectedVendors.includes(v) && selectedVendors.length >= 4}
                                />
                            ))}
                        </div>

                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginBottom: 'var(--sp-6)' }}>
                            {selectedVendors.length}/4 selected {selectedVendors.length < 2 && '(min 2)'}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <button className="btn btn-secondary" onClick={prevStep}>
                                <ArrowLeft size={14} /> Back
                            </button>
                            <button className="btn btn-primary" onClick={nextStep} disabled={selectedVendors.length < 2}>
                                Focus Areas <ArrowRight size={14} />
                            </button>
                        </div>
                    </div>
                )}

                {/* ═══════════════════════════════════════════════════════
                    SELLER STEP 2: MY COMPANY (single-select dropdown)
                   ═══════════════════════════════════════════════════════ */}
                {stepKey === 'MY_COMPANY' && mode === 'seller' && (
                    <div className="animate-fade-in">
                        <h2 style={{ marginBottom: 'var(--sp-2)', display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', fontSize: 'var(--text-lg)' }}>
                            <Briefcase size={20} style={{ color: 'var(--accent-purple)' }} /> Who do you sell for?
                        </h2>
                        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginBottom: 'var(--sp-6)' }}>
                            Select the vendor you represent. The battlecard will be generated from your perspective.
                        </p>

                        <div style={{ marginBottom: 'var(--sp-6)' }}>
                            <label className="input-label">Your Product</label>
                            <select className="input-field" value={myCompany} onChange={e => setMyCompany(e.target.value)}>
                                <option value="">— Select Your Company —</option>
                                {verticalVendors.map(v => (
                                    <option key={v} value={v}>{v}</option>
                                ))}
                            </select>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <button className="btn btn-secondary" onClick={prevStep}>
                                <ArrowLeft size={14} /> Back
                            </button>
                            <button className="btn btn-primary" onClick={nextStep} disabled={!myCompany}>
                                Select Competitors <ArrowRight size={14} />
                            </button>
                        </div>
                    </div>
                )}

                {/* ═══════════════════════════════════════════════════════
                    SELLER STEP 3: COMPETITORS (multi-select chips, 1-3)
                   ═══════════════════════════════════════════════════════ */}
                {stepKey === 'COMPETITORS' && mode === 'seller' && (
                    <div className="animate-fade-in">
                        <h2 style={{ marginBottom: 'var(--sp-2)', display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', fontSize: 'var(--text-lg)' }}>
                            <Crosshair size={20} style={{ color: 'var(--accent-red)' }} /> Who are you competing against?
                        </h2>
                        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginBottom: 'var(--sp-6)' }}>
                            Select 1–3 competitors in this deal.
                        </p>

                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-2)', marginBottom: 'var(--sp-6)' }}>
                            {verticalVendors.filter(v => v !== myCompany).map(v => (
                                <Chip
                                    key={v}
                                    label={v}
                                    selected={sellerCompetitors.includes(v)}
                                    onClick={() => toggleSellerComp(v)}
                                    disabled={!sellerCompetitors.includes(v) && sellerCompetitors.length >= 3}
                                />
                            ))}
                        </div>

                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginBottom: 'var(--sp-6)' }}>
                            {sellerCompetitors.length}/3 selected {sellerCompetitors.length < 1 && '(min 1)'}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <button className="btn btn-secondary" onClick={prevStep}>
                                <ArrowLeft size={14} /> Back
                            </button>
                            <button className="btn btn-primary" onClick={nextStep} disabled={sellerCompetitors.length < 1}>
                                Prospect Profile <ArrowRight size={14} />
                            </button>
                        </div>
                    </div>
                )}

                {/* ═══════════════════════════════════════════════════════
                    BUYER STEP 3: PROFILE
                   ═══════════════════════════════════════════════════════ */}
                {stepKey === 'PROFILE' && mode === 'buyer' && (
                    <div className="animate-fade-in">
                        <h2 style={{ marginBottom: 'var(--sp-6)', display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', fontSize: 'var(--text-lg)' }}>
                            <User size={20} style={{ color: 'var(--accent-cyan)' }} /> Your Profile
                        </h2>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-4)', marginBottom: 'var(--sp-6)' }}>
                            <div style={{ gridColumn: '1 / -1' }}>
                                <label className="input-label">Company Name *</label>
                                <input type="text" className="input-field" placeholder="e.g. Acme Corp" value={pCompany} onChange={e => setPCompany(e.target.value)} />
                            </div>
                            <div>
                                <label className="input-label">Team Size *</label>
                                <input type="text" className="input-field" placeholder="e.g. 10 engineers" value={pTeamSize} onChange={e => setPTeamSize(e.target.value)} />
                            </div>
                            <div>
                                <label className="input-label">Monthly Budget *</label>
                                <input type="text" className="input-field" placeholder="e.g. $5,000" value={pBudget} onChange={e => setPBudget(e.target.value)} />
                            </div>
                            <div style={{ gridColumn: '1 / -1' }}>
                                <label className="input-label">Primary Use Case *</label>
                                <input type="text" className="input-field" placeholder="e.g. RAG pipeline, semantic search" value={pUseCase} onChange={e => setPUseCase(e.target.value)} />
                            </div>
                            <div style={{ gridColumn: '1 / -1' }}>
                                <label className="input-label">Scale — current + 18 months *</label>
                                <input type="text" className="input-field" placeholder="e.g. 10M vectors now, 500M in 18mo" value={pScale} onChange={e => setPScale(e.target.value)} />
                            </div>
                            <div>
                                <label className="input-label">Cloud Provider</label>
                                <select className="input-field" value={pCloud} onChange={e => setPCloud(e.target.value)}>
                                    <option value="">— None —</option>
                                    <option value="AWS">AWS</option>
                                    <option value="GCP">GCP</option>
                                    <option value="Azure">Azure</option>
                                </select>
                            </div>
                            <div>
                                <label className="input-label">Top Priority</label>
                                <select className="input-field" value={pPriority} onChange={e => setPPriority(e.target.value)}>
                                    <option value="cost">Cost & Budget</option>
                                    <option value="performance">Raw Performance</option>
                                    <option value="simplicity">Simplicity / DX</option>
                                    <option value="no-lock-in">No Vendor Lock-in</option>
                                    <option value="enterprise">Enterprise Readiness</option>
                                </select>
                            </div>
                        </div>

                        {/* Session Summary */}
                        <div style={{
                            background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-md)',
                            padding: 'var(--sp-4)', marginBottom: 'var(--sp-6)',
                            border: '1px solid var(--border-subtle)',
                        }}>
                            <div className="section-title" style={{ marginBottom: 'var(--sp-2)' }}>Session Summary</div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)', fontSize: 'var(--text-sm)' }}>
                                <div><span style={{ color: 'var(--text-muted)' }}>Mode:</span> <span style={{ color: 'var(--accent-cyan)' }}>Buyer Evaluation</span></div>
                                <div><span style={{ color: 'var(--text-muted)' }}>Vertical:</span> <span style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>{vertical}</span></div>
                                <div style={{ gridColumn: '1 / -1' }}><span style={{ color: 'var(--text-muted)' }}>Vendors:</span> <span style={{ color: 'var(--accent-cyan)' }}>{selectedVendors.join(', ')}</span></div>
                            </div>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <button className="btn btn-secondary" onClick={prevStep}>
                                <ArrowLeft size={14} /> Back
                            </button>
                            <button className="btn btn-solid" onClick={initiateDeliberation} disabled={!isProfileComplete} style={{ background: 'var(--accent-red)', borderColor: 'var(--accent-red)' }}>
                                <Cpu size={14} /> Initiate Deliberation
                            </button>
                        </div>
                    </div>
                )}

                {/* ═══════════════════════════════════════════════════════
                    SELLER STEP 4: PROSPECT PROFILE
                   ═══════════════════════════════════════════════════════ */}
                {stepKey === 'PROSPECT' && mode === 'seller' && (
                    <div className="animate-fade-in">
                        <h2 style={{ marginBottom: 'var(--sp-6)', display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', fontSize: 'var(--text-lg)' }}>
                            <User size={20} style={{ color: 'var(--accent-purple)' }} /> Prospect Profile
                        </h2>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-4)', marginBottom: 'var(--sp-6)' }}>
                            <div style={{ gridColumn: '1 / -1' }}>
                                <label className="input-label">Prospect Company Name *</label>
                                <input type="text" className="input-field" placeholder="e.g. TechCorp" value={pCompany} onChange={e => setPCompany(e.target.value)} />
                            </div>
                            <div>
                                <label className="input-label">Prospect Team Size *</label>
                                <input type="text" className="input-field" placeholder="e.g. 20 engineers" value={pTeamSize} onChange={e => setPTeamSize(e.target.value)} />
                            </div>
                            <div>
                                <label className="input-label">Prospect Budget *</label>
                                <input type="text" className="input-field" placeholder="e.g. $10,000/mo" value={pBudget} onChange={e => setPBudget(e.target.value)} />
                            </div>
                            <div style={{ gridColumn: '1 / -1' }}>
                                <label className="input-label">Prospect Use Case *</label>
                                <input type="text" className="input-field" placeholder="e.g. SaaS platform, analytics" value={pUseCase} onChange={e => setPUseCase(e.target.value)} />
                            </div>
                            <div style={{ gridColumn: '1 / -1' }}>
                                <label className="input-label">Prospect Scale *</label>
                                <input type="text" className="input-field" placeholder="e.g. 100 VMs now, 500 in 18mo" value={pScale} onChange={e => setPScale(e.target.value)} />
                            </div>
                            <div>
                                <label className="input-label">Prospect Cloud</label>
                                <select className="input-field" value={pCloud} onChange={e => setPCloud(e.target.value)}>
                                    <option value="">— None —</option>
                                    <option value="AWS">AWS</option>
                                    <option value="GCP">GCP</option>
                                    <option value="Azure">Azure</option>
                                </select>
                            </div>
                            <div>
                                <label className="input-label">Prospect Top Priority</label>
                                <select className="input-field" value={pPriority} onChange={e => setPPriority(e.target.value)}>
                                    <option value="cost">Cost & Budget</option>
                                    <option value="performance">Raw Performance</option>
                                    <option value="simplicity">Simplicity / DX</option>
                                    <option value="no-lock-in">No Vendor Lock-in</option>
                                    <option value="enterprise">Enterprise Readiness</option>
                                </select>
                            </div>
                        </div>

                        {/* Session Summary */}
                        <div style={{
                            background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-md)',
                            padding: 'var(--sp-4)', marginBottom: 'var(--sp-6)',
                            border: '1px solid var(--border-subtle)',
                        }}>
                            <div className="section-title" style={{ marginBottom: 'var(--sp-2)' }}>Battlecard Summary</div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)', fontSize: 'var(--text-sm)' }}>
                                <div><span style={{ color: 'var(--text-muted)' }}>Mode:</span> <span style={{ color: 'var(--accent-purple)' }}>Seller Battlecard</span></div>
                                <div><span style={{ color: 'var(--text-muted)' }}>Vertical:</span> <span style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>{vertical}</span></div>
                                <div><span style={{ color: 'var(--text-muted)' }}>You Sell:</span> <span style={{ color: 'var(--accent-purple)' }}>{myCompany}</span></div>
                                <div><span style={{ color: 'var(--text-muted)' }}>Against:</span> <span style={{ color: 'var(--accent-red)' }}>{sellerCompetitors.join(', ')}</span></div>
                            </div>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <button className="btn btn-secondary" onClick={prevStep}>
                                <ArrowLeft size={14} /> Back
                            </button>
                            <button className="btn btn-solid" onClick={initiateDeliberation} disabled={!isProfileComplete} style={{ background: 'var(--accent-red)', borderColor: 'var(--accent-red)' }}>
                                <Cpu size={14} /> Generate Battlecard
                            </button>
                        </div>
                    </div>
                )}

                {/* ═══════════════════════════════════════════════════════
                    ANALYST STEP 3: FOCUS AREAS (optional)
                   ═══════════════════════════════════════════════════════ */}
                {stepKey === 'FOCUS' && mode === 'analyst' && (
                    <div className="animate-fade-in">
                        <h2 style={{ marginBottom: 'var(--sp-2)', display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', fontSize: 'var(--text-lg)' }}>
                            <BarChart3 size={20} style={{ color: 'var(--accent-green)' }} /> Focus Areas
                        </h2>
                        <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginBottom: 'var(--sp-6)' }}>
                            Focus comparison on specific areas? <strong>This step is optional</strong> — skip if you want a full comparison.
                        </p>

                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-2)', marginBottom: 'var(--sp-6)' }}>
                            {FOCUS_AREAS.map(f => (
                                <Chip
                                    key={f}
                                    label={f}
                                    selected={focusAreas.includes(f)}
                                    onClick={() => toggleFocus(f)}
                                />
                            ))}
                        </div>

                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginBottom: 'var(--sp-6)' }}>
                            {focusAreas.length > 0 ? `Focused on: ${focusAreas.join(', ')}` : 'No focus areas selected — full comparison will be generated.'}
                        </div>

                        {/* Session Summary */}
                        <div style={{
                            background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-md)',
                            padding: 'var(--sp-4)', marginBottom: 'var(--sp-6)',
                            border: '1px solid var(--border-subtle)',
                        }}>
                            <div className="section-title" style={{ marginBottom: 'var(--sp-2)' }}>Analysis Summary</div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)', fontSize: 'var(--text-sm)' }}>
                                <div><span style={{ color: 'var(--text-muted)' }}>Mode:</span> <span style={{ color: 'var(--accent-green)' }}>Analyst Comparison</span></div>
                                <div><span style={{ color: 'var(--text-muted)' }}>Vertical:</span> <span style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>{vertical}</span></div>
                                <div style={{ gridColumn: '1 / -1' }}><span style={{ color: 'var(--text-muted)' }}>Vendors:</span> <span style={{ color: 'var(--accent-green)' }}>{selectedVendors.join(', ')}</span></div>
                                {focusAreas.length > 0 && (
                                    <div style={{ gridColumn: '1 / -1' }}><span style={{ color: 'var(--text-muted)' }}>Focus:</span> <span style={{ color: 'var(--accent-yellow)' }}>{focusAreas.join(', ')}</span></div>
                                )}
                            </div>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <button className="btn btn-secondary" onClick={prevStep}>
                                <ArrowLeft size={14} /> Back
                            </button>
                            <button className="btn btn-solid" onClick={initiateDeliberation} style={{ background: 'var(--accent-green)', borderColor: 'var(--accent-green)' }}>
                                <Cpu size={14} /> Run Analysis
                            </button>
                        </div>
                    </div>
                )}

                {/* ═══════════════════════════════════════════════════════
                    DELIBERATING (all modes)
                   ═══════════════════════════════════════════════════════ */}
                {stepKey === 'DELIB' && (
                    <div className="animate-fade-in">
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 'var(--sp-4)',
                            marginBottom: 'var(--sp-6)',
                            padding: 'var(--sp-4)',
                            background: mode === 'seller' ? 'rgba(170,100,255,0.05)' : mode === 'analyst' ? 'rgba(0,255,136,0.05)' : 'rgba(255,68,102,0.05)',
                            borderRadius: 'var(--radius-md)',
                            border: `1px solid ${mode === 'seller' ? 'rgba(170,100,255,0.15)' : mode === 'analyst' ? 'rgba(0,255,136,0.15)' : 'rgba(255,68,102,0.15)'}`,
                        }}>
                            <ShieldAlert size={28} style={{
                                color: mode === 'seller' ? 'var(--accent-purple)' : mode === 'analyst' ? 'var(--accent-green)' : 'var(--accent-red)',
                                flexShrink: 0,
                            }} className="animate-pulse-glow" />
                            <div>
                                <h2 style={{
                                    color: mode === 'seller' ? 'var(--accent-purple)' : mode === 'analyst' ? 'var(--accent-green)' : 'var(--accent-red)',
                                    fontSize: 'var(--text-base)', marginBottom: 2,
                                }}>
                                    {mode === 'seller' ? 'Generating Battlecard...' : mode === 'analyst' ? 'Running Market Analysis...' : 'AI Court Session In Progress'}
                                </h2>
                                <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
                                    {mode === 'seller'
                                        ? `${myCompany} vs ${sellerCompetitors.join(', ')} — seller mode`
                                        : `${selectedVendors.join(' vs ')} — ${mode} mode`}
                                </p>
                            </div>
                        </div>

                        {session ? (
                            <TerminalLoader sessionId={session} onComplete={onSimulationComplete} />
                        ) : (
                            <div style={{
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                height: 200, color: 'var(--text-muted)', fontSize: 'var(--text-sm)',
                            }}>
                                Initializing connection to war room...
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
