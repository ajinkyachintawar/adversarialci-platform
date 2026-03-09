import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Copy, Download } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

export default function ReportView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchReport() {
      try {
        const res = await fetch(`http://localhost:8000/api/reports/${id}`);
        if (!res.ok) throw new Error('Failed to fetch report');
        const data = await res.json();
        setContent(data.content || data.verdict || '');
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    if (id) fetchReport();
  }, [id]);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${id}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading-state">Loading report...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container">
        <div className="error-state">Error: {error}</div>
      </div>
    );
  }

  // Detect mode from content
  const mode = content.includes('BATTLECARD') ? 'seller' 
    : content.includes('MARKET ANALYSIS') ? 'analyst' 
    : 'buyer';

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <button className="back-link" onClick={() => navigate('/history')}>
            <ArrowLeft size={16} /> Back to History
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '8px' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>[ID: {id}]</span>
            <span className={`mode-badge ${mode}`}>{mode.toUpperCase()}</span>
          </div>
          <h1 style={{ marginTop: '8px' }}>
            {mode === 'seller' ? 'Competitive Battlecard' : mode === 'analyst' ? 'Market Analysis' : 'Vendor Evaluation'}
          </h1>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn-secondary" onClick={handleCopy}>
            <Copy size={16} /> Copy
          </button>
          <button className="btn-secondary" onClick={handleDownload}>
            <Download size={16} /> Download
          </button>
        </div>
      </div>

      <div className="report-content" style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '24px',
        marginTop: '24px'
      }}>
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
