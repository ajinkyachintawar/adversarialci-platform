import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, X } from 'lucide-react';
import Skeleton from '../components/Skeleton';
import ErrorState from '../components/ErrorState';
import { useAllVendors } from '../hooks/useApi';
import { useAuth } from '../context/AuthContext';
import { authFetch } from '../lib/api';
import { PillFilter, LogTail } from '../components/design';

const ADMIN_KEY    = import.meta.env.VITE_ADMIN_KEY || '';

const SOURCE_ORDER = ['Pricing', 'Blog', 'GitHub', 'Tavily', 'HN', 'Migration', 'Complaints'];

type VerticalKey = 'all' | 'database' | 'cloud' | 'crm';

interface AtlasData {
    research_count: number;
    sources: Record<string, number>;
    last_scraped: string | null;
    status: string;
}

interface EnrichedVendor {
    name: string;
    vertical: string;
    pricing_url: string | null;
    github_repo: string | null;
    blog_rss: string[];
    blog_tavily: string[];
    migration_queries: string[];
    complaint_queries: string[];
    atlas: AtlasData | null;
}

interface RefreshState { lines: string[]; done: boolean; }

function initials(name: string): string {
    const clean = name.trim();
    if (!clean) return '··';
    return clean.slice(0, 2).toUpperCase();
}

function freshMeta(status: string | undefined) {
    if (status === 'fresh') return { label: 'Fresh', bg: 'var(--success-15)', color: 'var(--success)' };
    if (status === 'stale') return { label: 'Stale', bg: 'var(--warn-15)',    color: 'var(--warn)' };
    return { label: 'New', bg: 'var(--surface-3)', color: 'var(--text-3)' };
}

function formatLastScraped(dateStr: string | null): string {
    if (!dateStr) return 'never';
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return dateStr;
    const now = new Date();
    const diffH = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60));
    if (diffH < 1)  return 'just now';
    if (diffH < 24) return `${diffH}h ago`;
    const diffD = Math.floor(diffH / 24);
    if (diffD < 30) return `${diffD}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function VendorRegistry() {
    const { session } = useAuth();
    const isAdmin = !!session;
    const navigate = useNavigate();

    const [search, setSearch] = useState('');
    const [vertical, setVertical] = useState<VerticalKey>('all');
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [showAddModal, setShowAddModal] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<{ name: string; vertical: string } | null>(null);
    const [refreshing, setRefreshing] = useState<Record<string, RefreshState>>({});
    const refreshTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

    const { data: vendorData, isLoading, error: queryError, refetch } = useAllVendors();

    const allVendors: EnrichedVendor[] = vendorData
        ? [...(vendorData.database || []), ...(vendorData.cloud || []), ...(vendorData.crm || [])]
        : [];

    const q = search.trim().toLowerCase();
    const filtered = allVendors.filter(v => {
        if (vertical !== 'all' && v.vertical !== vertical) return false;
        if (q && !v.name.toLowerCase().includes(q)) return false;
        return true;
    });

    const handleRefresh = (name: string, vert: string) => {
        setRefreshing(prev => ({ ...prev, [name]: { lines: ['[connecting…]'], done: false } }));

        authFetch(`/api/vendors/refresh`, {
            method: 'POST',
            headers: { 'X-Admin-Key': ADMIN_KEY },
            body: JSON.stringify({ name, vertical: vert }),
        }).then(async response => {
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            if (!reader) return;

            let buffer = '';
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                for (const line of lines) {
                    if (!line.startsWith('data:')) continue;
                    const data = line.substring(5).trim();
                    if (data === 'keep-alive') continue;

                    if (data.startsWith('__REFRESH_DONE__:')) {
                        setRefreshing(prev => ({
                            ...prev,
                            [name]: { lines: [...(prev[name]?.lines || []), '✓ scrape complete'], done: true },
                        }));
                        refreshTimers.current[name] = setTimeout(() => {
                            setRefreshing(prev => {
                                const next = { ...prev };
                                delete next[name];
                                return next;
                            });
                            refetch();
                        }, 1600);
                        return;
                    }

                    setRefreshing(prev => ({
                        ...prev,
                        [name]: {
                            lines: [...(prev[name]?.lines || []), data].slice(-8),
                            done: false,
                        },
                    }));
                }
            }
        }).catch(err => {
            setRefreshing(prev => ({
                ...prev,
                [name]: { lines: [`✗ error: ${err.message}`], done: true },
            }));
            refreshTimers.current[name] = setTimeout(() => {
                setRefreshing(prev => {
                    const next = { ...prev };
                    delete next[name];
                    return next;
                });
            }, 2500);
        });
    };

    const handleDelete = async (name: string, vert: string) => {
        try {
            const res = await authFetch(`/api/vendors`, {
                method: 'DELETE',
                headers: { 'X-Admin-Key': ADMIN_KEY },
                body: JSON.stringify({ name, vertical: vert }),
            });
            if (res.ok) {
                setDeleteTarget(null);
                setExpandedId(null);
                refetch();
            }
        } catch (e) {
            console.error('Delete failed:', e);
        }
    };

    if (queryError) {
        return (
            <div style={{ padding: '36px 44px' }} className="animate-fade-in">
                <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.02em', margin: '0 0 24px' }}>
                    Vendor Registry
                </h1>
                <ErrorState message="Failed to load vendor data." onRetry={refetch} />
            </div>
        );
    }

    return (
        <div style={{ padding: '36px 44px' }} className="animate-fade-in">
            {!isAdmin && (
                <div style={{
                    background: 'var(--warn-10)',
                    border: '1px solid var(--warn-30)',
                    borderRadius: 10,
                    padding: '12px 16px',
                    fontSize: 13,
                    color: 'var(--warn)',
                    marginBottom: 22,
                    display: 'flex', alignItems: 'center', gap: 10,
                }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>[RO]</span>
                    <span>
                        Read-only mode —{' '}
                        <span
                            onClick={() => navigate('/login')}
                            style={{ textDecoration: 'underline', cursor: 'pointer' }}
                        >
                            <Lock size={11} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                            sign in
                        </span>
                        {' '}to add, edit, or re-scrape vendors.
                    </span>
                </div>
            )}

            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: 24,
            }}>
                <div>
                    <h1 style={{
                        fontSize: 26, fontWeight: 800, margin: '0 0 4px',
                        letterSpacing: '-0.02em',
                    }}>Vendor Registry</h1>
                    <p style={{ fontSize: 14, color: 'var(--text-3)', margin: 0 }}>
                        {isLoading
                            ? 'Loading vendor intel…'
                            : `${filtered.length} of ${allVendors.length} vendors`}
                    </p>
                </div>
                {isAdmin && (
                    <button
                        onClick={() => setShowAddModal(true)}
                        style={{
                            background: 'var(--accent)', color: 'var(--bg)', border: 'none',
                            padding: '11px 18px', borderRadius: 9,
                            fontFamily: 'inherit', fontSize: 14, fontWeight: 700, cursor: 'pointer',
                        }}
                    >
                        + Add vendor
                    </button>
                )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 22, flexWrap: 'wrap' }}>
                <input
                    type="text"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Search vendors…"
                    style={{
                        flex: 1, maxWidth: 320,
                        background: 'oklch(1 0 0 / 0.04)',
                        border: '1px solid var(--line-2)',
                        borderRadius: 9,
                        padding: '10px 14px',
                        color: 'var(--text)',
                        fontFamily: 'inherit',
                        fontSize: 14,
                        outline: 'none',
                    }}
                />
                <PillFilter<VerticalKey>
                    options={[
                        { key: 'all',      label: 'All verticals' },
                        { key: 'database', label: 'Database' },
                        { key: 'cloud',    label: 'Cloud' },
                        { key: 'crm',      label: 'CRM' },
                    ]}
                    value={vertical}
                    onChange={setVertical}
                />
            </div>

            {isLoading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} height={72} />)}
                </div>
            ) : filtered.length === 0 ? (
                <div style={{
                    background: 'var(--surface-1)', border: '1px solid var(--line)',
                    borderRadius: 14, padding: '48px 24px', textAlign: 'center',
                    color: 'var(--text-3)', fontSize: 14,
                }}>
                    No vendors match this filter.
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {filtered.map(v => (
                        <VendorCard
                            key={`${v.vertical}:${v.name}`}
                            vendor={v}
                            expanded={expandedId === `${v.vertical}:${v.name}`}
                            onToggle={() => setExpandedId(prev =>
                                prev === `${v.vertical}:${v.name}` ? null : `${v.vertical}:${v.name}`
                            )}
                            refresh={refreshing[v.name]}
                            isAdmin={isAdmin}
                            onRefresh={() => handleRefresh(v.name, v.vertical)}
                            onEdit={() => {
                                // TODO: wire up PUT /api/vendors edit modal.
                                // Backend endpoint exists but has an admin-key auth gap
                                // that needs closing before we expose UI for it.
                                console.warn('Edit vendor: not yet wired', v.name);
                                alert(`Edit ${v.name} — coming soon (PUT /api/vendors endpoint needs auth-gap fix).`);
                            }}
                            onRemove={() => setDeleteTarget({ name: v.name, vertical: v.vertical })}
                        />
                    ))}
                </div>
            )}

            {showAddModal && (
                <AddVendorModal
                    onClose={() => setShowAddModal(false)}
                    onSuccess={() => { setShowAddModal(false); refetch(); }}
                />
            )}
            {deleteTarget && (
                <DeleteConfirmModal
                    target={deleteTarget}
                    onCancel={() => setDeleteTarget(null)}
                    onConfirm={() => handleDelete(deleteTarget.name, deleteTarget.vertical)}
                />
            )}
        </div>
    );
}

/* ─── Vendor card ───────────────────────────────────────────── */

function VendorCard({
    vendor, expanded, onToggle, refresh, isAdmin, onRefresh, onEdit, onRemove,
}: {
    vendor: EnrichedVendor;
    expanded: boolean;
    onToggle: () => void;
    refresh?: RefreshState;
    isAdmin: boolean;
    onRefresh: () => void;
    onEdit: () => void;
    onRemove: () => void;
}) {
    const fm = freshMeta(vendor.atlas?.status);
    const sources = vendor.atlas?.sources || {};
    const docTotal = vendor.atlas?.research_count
        ?? Object.values(sources).reduce((a, b) => a + b, 0);

    const isRefreshing = !!refresh && !refresh.done;

    return (
        <div style={{
            background: 'var(--surface-1)',
            border: '1px solid var(--line)',
            borderRadius: 14,
            overflow: 'hidden',
        }}>
            <div
                onClick={onToggle}
                style={{
                    display: 'flex', alignItems: 'center', gap: 16,
                    padding: '16px 20px', cursor: 'pointer',
                }}
            >
                <div style={{
                    width: 38, height: 38, borderRadius: 10,
                    background: 'var(--surface-2)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 13, fontWeight: 700, color: 'var(--accent)',
                    flexShrink: 0,
                }}>{initials(vendor.name)}</div>

                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: 15, fontWeight: 700 }}>{vendor.name}</span>
                        <span style={{
                            fontSize: 11, padding: '2px 8px', borderRadius: 100,
                            background: 'var(--surface-3)', color: 'var(--text-3)',
                            fontFamily: 'var(--font-mono)',
                        }}>{vendor.vertical}</span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 3 }}>
                        {docTotal} intel docs · last scraped {formatLastScraped(vendor.atlas?.last_scraped ?? null)}
                    </div>
                </div>

                <span style={{
                    fontSize: 12, padding: '4px 10px', borderRadius: 100,
                    background: fm.bg, color: fm.color, fontWeight: 600, flexShrink: 0,
                }}>{fm.label}</span>

                <span style={{
                    color: 'var(--text-3)', fontSize: 12,
                    transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.15s',
                }}>▾</span>
            </div>

            {expanded && (
                <div style={{
                    padding: '4px 20px 22px',
                    borderTop: '1px solid var(--surface-3)',
                }}>
                    <div style={{
                        display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
                        gap: 10, margin: '16px 0 20px',
                    }}>
                        {SOURCE_ORDER.map(label => (
                            <div key={label} style={{
                                background: 'var(--surface-1)',
                                borderRadius: 10,
                                padding: 10,
                                textAlign: 'center',
                            }}>
                                <div style={{
                                    fontFamily: 'var(--font-mono)', fontSize: 17, fontWeight: 700,
                                    color: 'var(--accent)',
                                }}>{sources[label] ?? 0}</div>
                                <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 4 }}>{label}</div>
                            </div>
                        ))}
                    </div>

                    {vendor.pricing_url && (
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 16,
                            fontSize: 13, color: 'var(--text-3)', marginBottom: 14,
                        }}>
                            <span>
                                Pricing:{' '}
                                <a
                                    href={vendor.pricing_url.startsWith('http')
                                        ? vendor.pricing_url
                                        : `https://${vendor.pricing_url}`}
                                    target="_blank" rel="noreferrer"
                                    style={{ color: 'var(--accent)' }}
                                >{vendor.pricing_url}</a>
                            </span>
                        </div>
                    )}
                    {vendor.github_repo && (
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 16,
                            fontSize: 13, color: 'var(--text-3)', marginBottom: 20,
                        }}>
                            <span>
                                GitHub:{' '}
                                <a
                                    href={`https://github.com/${vendor.github_repo}`}
                                    target="_blank" rel="noreferrer"
                                    style={{ color: 'var(--accent)' }}
                                >{vendor.github_repo}</a>
                            </span>
                        </div>
                    )}

                    {refresh && (
                        <div style={{ marginBottom: 14 }}>
                            <LogTail lines={refresh.lines} variant="inline" />
                        </div>
                    )}

                    {isAdmin && (
                        <div style={{ display: 'flex', gap: 10 }}>
                            <button
                                onClick={onRefresh}
                                disabled={isRefreshing}
                                style={{
                                    background: 'var(--surface-3)',
                                    border: '1px solid var(--line-2)',
                                    color: 'var(--text)',
                                    padding: '8px 14px', borderRadius: 8,
                                    fontFamily: 'inherit', fontSize: 12, fontWeight: 600,
                                    cursor: isRefreshing ? 'default' : 'pointer',
                                    opacity: isRefreshing ? 0.5 : 1,
                                }}
                            >
                                ↻ Re-scrape
                            </button>
                            <button
                                onClick={onEdit}
                                style={{
                                    background: 'var(--surface-3)',
                                    border: '1px solid var(--line-2)',
                                    color: 'var(--text)',
                                    padding: '8px 14px', borderRadius: 8,
                                    fontFamily: 'inherit', fontSize: 12, fontWeight: 600,
                                    cursor: 'pointer',
                                }}
                            >
                                Edit
                            </button>
                            <button
                                onClick={onRemove}
                                style={{
                                    background: 'var(--danger-10)',
                                    border: '1px solid var(--danger-30)',
                                    color: 'var(--danger)',
                                    padding: '8px 14px', borderRadius: 8,
                                    fontFamily: 'inherit', fontSize: 12, fontWeight: 600,
                                    cursor: 'pointer',
                                }}
                            >
                                Delete
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

/* ─── Modals (existing behavior, restyled to tokens) ────────── */

function AddVendorModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
    const [form, setForm] = useState({
        name: '', vertical: 'database', pricing_url: '', github_repo: '', blog_rss: '',
    });
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const submit = async () => {
        if (!form.name.trim() || !form.pricing_url.trim()) {
            setError('Name and Pricing URL are required.');
            return;
        }
        setSubmitting(true);
        setError('');
        try {
            const res = await authFetch(`/api/vendors`, {
                method: 'POST',
                headers: { 'X-Admin-Key': ADMIN_KEY },
                body: JSON.stringify({
                    name: form.name.trim(),
                    vertical: form.vertical,
                    pricing_url: form.pricing_url.trim(),
                    github_repo: form.github_repo.trim() || null,
                    blog_rss: form.blog_rss.trim() || null,
                }),
            });
            if (res.ok) {
                onSuccess();
            } else {
                const data = await res.json();
                setError(data.detail || 'Failed to add vendor');
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" style={{ maxWidth: 500 }} onClick={e => e.stopPropagation()}>
                <div style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    marginBottom: 20,
                }}>
                    <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent)' }}>+ Add Vendor</h2>
                    <button onClick={onClose} style={{ color: 'var(--text-3)' }}><X size={18} /></button>
                </div>

                {error && (
                    <div style={{
                        padding: 12, borderRadius: 6,
                        background: 'var(--danger-10)', border: '1px solid var(--danger)',
                        color: 'var(--danger)', fontSize: 13, marginBottom: 16,
                    }}>{error}</div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div>
                        <label className="input-label">Vendor Name *</label>
                        <input className="input-field" placeholder="e.g. MongoDB, Snowflake"
                            value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
                    </div>
                    <div>
                        <label className="input-label">Vertical *</label>
                        <select className="input-field" value={form.vertical}
                            onChange={e => setForm({ ...form, vertical: e.target.value })}>
                            <option value="database">Database</option>
                            <option value="cloud">Cloud</option>
                            <option value="crm">CRM</option>
                        </select>
                    </div>
                    <div>
                        <label className="input-label">Pricing URL *</label>
                        <input className="input-field" placeholder="https://example.com/pricing"
                            value={form.pricing_url}
                            onChange={e => setForm({ ...form, pricing_url: e.target.value })} />
                    </div>
                    <div>
                        <label className="input-label">GitHub Repo</label>
                        <input className="input-field" placeholder="owner/repo"
                            value={form.github_repo}
                            onChange={e => setForm({ ...form, github_repo: e.target.value })} />
                    </div>
                    <div>
                        <label className="input-label">Blog RSS Feed</label>
                        <input className="input-field" placeholder="https://example.com/blog/rss"
                            value={form.blog_rss}
                            onChange={e => setForm({ ...form, blog_rss: e.target.value })} />
                    </div>
                </div>

                <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 20 }}>
                    <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
                    <button className="btn btn-solid" onClick={submit} disabled={submitting}>
                        {submitting ? 'Adding…' : 'Add Vendor'}
                    </button>
                </div>
            </div>
        </div>
    );
}

function DeleteConfirmModal({
    target, onCancel, onConfirm,
}: {
    target: { name: string; vertical: string };
    onCancel: () => void;
    onConfirm: () => void;
}) {
    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="modal-content" style={{ maxWidth: 440 }} onClick={e => e.stopPropagation()}>
                <div style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    marginBottom: 20,
                }}>
                    <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--danger)' }}>Delete Vendor</h2>
                    <button onClick={onCancel} style={{ color: 'var(--text-3)' }}><X size={18} /></button>
                </div>
                <p style={{
                    color: 'var(--text-2)', marginBottom: 8, lineHeight: 1.6, fontSize: 13,
                }}>
                    Delete <strong style={{ color: 'var(--text)' }}>{target.name}</strong> from the{' '}
                    <strong>{target.vertical}</strong> vertical?
                </p>
                <p style={{ color: 'var(--text-3)', fontSize: 12, marginBottom: 20 }}>
                    Atlas research data will be preserved.
                </p>
                <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                    <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
                    <button className="btn btn-danger" onClick={onConfirm}>Delete</button>
                </div>
            </div>
        </div>
    );
}
