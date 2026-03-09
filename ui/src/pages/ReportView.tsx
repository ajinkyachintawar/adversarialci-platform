import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Copy, Download } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { parseReport } from '../lib/reportParser';
import type { ParsedReport } from '../lib/reportParser';
import { WinnerCard, BattlecardHeader } from '../components/report';

export default function ReportView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [content, setContent] = useState<string>('');
  const [parsed, setParsed] = useState<ParsedReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchReport() {
      try {
        const res = await fetch(`http://localhost:8000/api/reports/${id}`);
        if (!res.ok) throw new Error('Failed to fetch report');
        const data = await res.json();
        const rawContent = data.content || data.verdict || '';
        setContent(rawContent);
        setParsed(parseReport(rawContent));
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
  const mode = parsed?.mode || 'buyer';

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
            {parsed?.title || (mode === 'seller' ? 'Competitive Battlecard' : mode === 'analyst' ? 'Market Analysis' : 'Vendor Evaluation')}
          </h1>
          {parsed?.subtitle && (
            <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0' }}>{parsed.subtitle}</p>
          )}
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

      {parsed?.mode === 'buyer' && (
        <WinnerCard
          winner={extractWinner(content)}
          confidence={extractConfidence(content)}
          summary={extractSummary(content)}
        />
      )}

      {parsed?.mode === 'seller' && (
        <BattlecardHeader
          winProbability={extractWinProbability(content)}
          isFavorite={content.includes("YOU'RE THE FAVORITE")}
          dimensionsWon={extractDimensionsWon(content)}
        />
      )}

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

function extractWinner(content: string): string {
  const match = content.match(/BEST FIT FOR YOU:\s*(\w+)/i)
    || content.match(/🏆\s*BEST FIT FOR YOU:\s*(\w+)/i);
  return match ? match[1] : '';
}

function extractConfidence(content: string): number {
  const match = content.match(/CONFIDENCE:\s*(\d+)%/i);
  return match ? parseInt(match[1]) : 0;
}

function extractSummary(content: string): string {
  const match = content.match(/WHY:\s*([^\n]+)/i);
  return match ? match[1].trim() : '';
}

function extractWinProbability(content: string): number {
  const match = content.match(/WIN PROBABILITY:\s*(\d+)%/i);
  return match ? parseInt(match[1]) : 0;
}

function extractDimensionsWon(content: string): string {
  const match = content.match(/You won (\d+\/\d+ dimensions)/i);
  return match ? match[1] : '';
}

