/**
 * Report Parser
 * Parses raw ASCII report text into structured sections for React rendering.
 */

export type ReportMode = 'buyer' | 'seller' | 'analyst';

export interface ParsedReport {
    mode: ReportMode;
    title: string;
    subtitle: string;
    generatedAt: string;
    sections: ReportSection[];
}

export interface ReportSection {
    icon: string;
    title: string;
    content: string;
    type: 'text' | 'matrix' | 'list' | 'progress';
}

export function parseReport(rawText: string): ParsedReport {
    // Detect mode from content
    let mode: ReportMode = 'buyer';
    if (rawText.includes('BATTLECARD') || rawText.includes('WIN PROBABILITY')) {
        mode = 'seller';
    } else if (rawText.includes('MARKET ANALYSIS') || rawText.includes('Objective Analysis')) {
        mode = 'analyst';
    }

    // Extract title (first non-empty line after header decoration)
    const lines = rawText.split('\n');
    let title = '';
    let subtitle = '';
    let generatedAt = '';

    for (const line of lines) {
        if (line.includes('VERDICT REPORT') || line.includes('BATTLECARD') || line.includes('MARKET ANALYSIS')) {
            title = line.replace(/[┌┐└┘│─━═]/g, '').trim();
        }
        if (line.includes('Generated:')) {
            generatedAt = line.split('Generated:')[1]?.trim() || '';
        }
        if (line.includes(' vs ')) {
            subtitle = line.trim();
        }
    }

    // Split into sections by section headers (lines with emoji + ALL CAPS)
    const sectionRegex = /^[─━═]*\s*([📊📋💪⚠️💣🗣️🚫🛡️📞🏆✅❌⭐🎯🛒])\s*([A-Z][A-Z\s&]+)/gm;
    const sections: ReportSection[] = [];

    let lastIndex = 0;
    let match;
    const rawSections: { icon: string; title: string; startIndex: number }[] = [];

    // Find all section headers
    const textForMatching = rawText;
    const regex = /[─━═]*\s*([📊📋💪⚠️💣🗣️🚫🛡️📞🏆✅❌⭐🎯🛒])\s+([A-Z][A-Z\s&]+)/g;

    while ((match = regex.exec(textForMatching)) !== null) {
        rawSections.push({
            icon: match[1],
            title: match[2].trim(),
            startIndex: match.index
        });
    }

    // Extract content for each section
    for (let i = 0; i < rawSections.length; i++) {
        const start = rawSections[i].startIndex;
        const end = i + 1 < rawSections.length ? rawSections[i + 1].startIndex : rawText.length;
        const content = rawText.slice(start, end)
            .split('\n')
            .slice(1) // Skip the header line
            .join('\n')
            .trim();

        // Determine section type
        let type: 'text' | 'matrix' | 'list' | 'progress' = 'text';
        if (content.includes('│') && content.includes('─')) {
            type = 'matrix';
        } else if (content.includes('████') || content.includes('░░░')) {
            type = 'progress';
        } else if (content.match(/^\s*[▸•✅⚠️❌]\s/m)) {
            type = 'list';
        }

        sections.push({
            icon: rawSections[i].icon,
            title: rawSections[i].title,
            content,
            type
        });
    }

    return {
        mode,
        title: title || 'Report',
        subtitle,
        generatedAt,
        sections
    };
}
