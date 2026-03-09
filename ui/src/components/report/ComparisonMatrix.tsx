interface ComparisonMatrixProps {
    headers: string[];
    rows: {
        dimension: string;
        cells: { vendor: string; isWin: boolean }[];
    }[];
}

export function ComparisonMatrix({ headers, rows }: ComparisonMatrixProps) {
    return (
        <div style={{ overflowX: 'auto', margin: '16px 0' }}>
            <table style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '14px'
            }}>
                <thead>
                    <tr>
                        <th style={{
                            textAlign: 'left',
                            padding: '12px',
                            background: '#1a1a24',
                            color: '#00d4ff',
                            fontWeight: 600,
                            borderBottom: '1px solid #2a2a3a'
                        }}>
                            Dimension
                        </th>
                        {headers.map((header, i) => (
                            <th key={i} style={{
                                textAlign: 'center',
                                padding: '12px',
                                background: '#1a1a24',
                                color: '#ffffff',
                                fontWeight: 600,
                                borderBottom: '1px solid #2a2a3a'
                            }}>
                                {header}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row, i) => (
                        <tr key={i} style={{
                            background: i % 2 === 0 ? '#12121a' : '#0a0a0f'
                        }}>
                            <td style={{
                                padding: '12px',
                                color: '#00d4ff',
                                borderBottom: '1px solid #2a2a3a'
                            }}>
                                {row.dimension}
                            </td>
                            {row.cells.map((cell, j) => (
                                <td key={j} style={{
                                    textAlign: 'center',
                                    padding: '12px',
                                    borderBottom: '1px solid #2a2a3a',
                                    color: cell.isWin ? '#00ff88' : '#8a8a9a'
                                }}>
                                    {cell.isWin ? '✅ WIN' : '—'}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
