import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Copy, Download } from 'lucide-react';
import { useReport } from '../hooks/useApi';
import {
  parseReport,
  extractWinner,
  extractConfidence,
  extractSummary,
  extractWinProbability,
  extractDimensionsWon,
} from '../lib/reportParser';
import { WinnerCard, BattlecardHeader, ReportBody } from '../components/report';


export default function ReportView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);

  const { data, isLoading: loading, error: queryError } = useReport(id);
  const content = data?.content || data?.verdict || '';
  const error = queryError ? (queryError as Error).message : null;
  const parsed = content ? parseReport(content) : null;

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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

  const mode = parsed?.mode || 'buyer';

  return (
    <div className="page-container">
      {/* Header */}
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
            {parsed?.title || (mode === 'seller' ? 'Competitive Battlecard' : mode === 'analyst' ? 'Market Analysis' : 'Vendor Evaluation')}
          </h1>
          {parsed?.subtitle && (
            <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0' }}>{parsed.subtitle}</p>
          )}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={handleCopy}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '8px 16px', background: 'transparent',
              border: '1px solid #2a2a3a', borderRadius: '6px',
              color: '#ffffff', fontSize: '13px', cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = '#1a1a24'; e.currentTarget.style.borderColor = '#00d4ff'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = '#2a2a3a'; }}
          >
            <Copy size={14} />
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            onClick={handleDownload}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '8px 16px', background: '#00d4ff',
              border: 'none', borderRadius: '6px',
              color: '#0a0a0f', fontSize: '13px', fontWeight: 600,
              cursor: 'pointer', transition: 'all 0.2s ease'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = '#00b8e6'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = '#00d4ff'; }}
          >
            <Download size={14} />
            Download
          </button>
        </div>
      </div>

      {/* Hero Card */}
      {mode === 'buyer' && (
        <WinnerCard
          winner={extractWinner(content)}
          confidence={extractConfidence(content)}
          summary={extractSummary(content)}
        />
      )}

      {mode === 'seller' && (
        <BattlecardHeader
          winProbability={extractWinProbability(content)}
          isFavorite={content.includes("YOU'RE THE FAVORITE")}
          dimensionsWon={extractDimensionsWon(content)}
        />
      )}

      {/* Report Body */}
      <ReportBody content={content} mode={mode} />
    </div>
  );
}
