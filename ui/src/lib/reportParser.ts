/**
 * Report Parser
 * Extracts structured data from raw ASCII report text for React rendering.
 */

export type ReportMode = 'buyer' | 'seller' | 'analyst';

export interface ParsedReport {
    mode: ReportMode;
    title: string;
    subtitle: string;
    generatedAt: string;
}

export interface ProfileData {
    company: string;
    team: string;
    budget: string;
    useCase: string;
    scale: string;
    priority: string;
}

export interface ScorecardDimension {
    name: string;
    results: Record<string, boolean>; // vendorName → isWin
}

export interface ScorecardData {
    vendors: string[];
    dimensions: ScorecardDimension[];
    summary: string;
}

export interface DimensionDetail {
    name: string;
    winner: string;
    why: string;
    isPriority: boolean;
}

export interface TradeoffsData {
    chosenVendor: string;
    benefits: string[];
    sacrifices: string[];
}

export interface RunnerUpData {
    vendor: string;
    reason: string;
    swingFactor: string;
}

export interface ConfidenceData {
    overall: number;
    label: string;
    dimensionsWon: string;
    priorityWon: boolean;
    dominance: string;
}

export interface AdvantageItem {
    title: string;
    quote: string;
    tip: string;
    isPriority: boolean;
}

export interface VulnerabilityItem {
    title: string;
    competitor: string;
    quote: string;
    tip: string;
}

export interface LandmineData {
    theySay: string[];
    youSay: string;
}

export interface TalkTrackData {
    opening: string;
    keyPoints: string[];
    close: string;
}

export interface ObjectionItem {
    objection: string;
    response: string;
}

export interface NextStepGroup {
    phase: string;
    items: string[];
}

// ─── Analyst Interfaces ────────────────────────────────────────

export interface AnalystSummary {
    description: string;
    dimensionWins: { vendor: string; wins: number; total: number }[];
}

export interface DimensionAnalysis {
    dimension: string;
    leader: string;
    analysis: string;
}

export interface VendorProfile {
    vendor: string;
    strengths: string[];
    weaknesses: string[];
}

export interface BestFitScenario {
    vendor: string;
    conditions: string[];
}

export interface AnalystTradeoff {
    title: string;
    lines: string[];
}

export interface DataQuality {
    score: string;
    details: string[];
    caveats: string[];
}

export interface MethodologyStep {
    name: string;
    description: string;
}

// ─── Helpers ───────────────────────────────────────────────────

/** Get raw text between two section headers */
function getSection(content: string, sectionName: string | RegExp): string {
    const lines = content.split('\n');
    let capturing = false;
    let result: string[] = [];

    const match = typeof sectionName === 'string'
        ? (line: string) => line.toUpperCase().includes(sectionName.toUpperCase())
        : (line: string) => sectionName.test(line);

    for (const line of lines) {
        if (capturing) {
            // Stop at next section header (line of ━ followed by emoji header)
            if (/^[━═─]{4,}/.test(line.trim()) && result.length > 0) {
                break;
            }
            result.push(line);
        } else if (match(line)) {
            capturing = true;
        }
    }

    // Remove leading/trailing separator lines
    while (result.length && /^[━═─]{4,}$/.test(result[0].trim())) result.shift();
    while (result.length && /^[━═─]{4,}$/.test(result[result.length - 1].trim())) result.pop();

    return result.join('\n').trim();
}

function cleanLine(line: string): string {
    return line.replace(/^\s*[•▸-]\s*/, '').trim();
}

// ─── Core Parser ───────────────────────────────────────────────

export function parseReport(rawText: string): ParsedReport {
    let mode: ReportMode = 'buyer';
    if (rawText.includes('BATTLECARD') || rawText.includes('WIN PROBABILITY')) {
        mode = 'seller';
    } else if (rawText.includes('MARKET ANALYSIS') || rawText.includes('Objective Analysis')) {
        mode = 'analyst';
    }

    const lines = rawText.split('\n');
    let title = '';
    let subtitle = '';
    let generatedAt = '';

    for (const line of lines) {
        const stripped = line.replace(/[╔╗╚╝║═┌┐└┘│─━]/g, '').trim();
        if (!title && (stripped.includes('BUYER RECOMMENDATION') || stripped.includes('BATTLECARD') || stripped.includes('MARKET ANALYSIS'))) {
            title = stripped;
        }
        if (line.includes('Generated:')) {
            generatedAt = line.split('Generated:')[1]?.replace(/[║╗╝]/g, '').trim() || '';
        }
        if (!subtitle && line.includes(' vs ')) {
            subtitle = line.replace(/[║]/g, '').trim();
        }
    }

    return { mode, title: title || 'Report', subtitle, generatedAt };
}

// ─── Buyer Extractors ──────────────────────────────────────────

export function extractWinner(content: string): string {
    const m = content.match(/BEST FIT FOR YOU:\s*(.+)/i);
    return m ? m[1].trim() : '';
}

export function extractConfidence(content: string): number {
    const m = content.match(/CONFIDENCE:\s*(\d+)%/i);
    return m ? parseInt(m[1]) : 0;
}

export function extractSummary(content: string): string {
    const m = content.match(/WHY:\s*([^\n]+)/i);
    return m ? m[1].trim() : '';
}

export function extractProfile(content: string): ProfileData | null {
    const section = getSection(content, 'YOUR PROFILE') || getSection(content, 'TARGET PROSPECT');
    if (!section) return null;

    const get = (key: string) => {
        const m = section.match(new RegExp(`${key}\\s*:\\s*(.+)`, 'i'));
        return m ? m[1].trim() : '';
    };

    return {
        company: get('Company'),
        team: get('Team'),
        budget: get('Budget'),
        useCase: get('Use Case'),
        scale: get('Scale'),
        priority: get('Top Priority') || get('TOP PRIORITY'),
    };
}

export function extractScorecard(content: string): ScorecardData | null {
    const section = getSection(content, /HOW VENDORS SCORED|VENDORS SCORED/);
    if (!section) return null;

    // Find vendor lines with ✅ or — markers
    const vendorLines = section.match(
        /^\s*(MongoDB|ChromaDB|Pinecone|Weaviate|Apache Cassandra|Amazon DocumentDB|Salesforce|HubSpot|Microsoft Dynamics|AWS|Azure|GCP|Google Cloud).+$/gim
    );
    if (!vendorLines || vendorLines.length === 0) return null;

    // Extract header row to get dimension names
    const headerLine = section.match(/^\s*Vendor\s+(.+)$/im);
    let dimNames = ['Cost', 'Performance', 'Scalability', 'Simplicity', 'Lock-In Risk', 'Vector Capability'];
    if (headerLine) {
        dimNames = headerLine[1].split(/\s{2,}/).map(d => d.trim()).filter(Boolean);
    }

    const vendors: string[] = [];
    const vendorResults: Record<string, boolean[]> = {};

    for (const vl of vendorLines) {
        // Split the line: first part is vendor name, then columns of ✅ WIN or —
        const vendorMatch = vl.match(/^\s*(.+?)\s{2,}/);
        if (!vendorMatch) continue;
        const vendorName = vendorMatch[1].trim();
        vendors.push(vendorName);

        // Extract column values after vendor name
        const rest = vl.slice(vendorMatch[0].length);
        const cols = rest.split(/\s{2,}/).map(c => c.trim());
        vendorResults[vendorName] = cols.map(c => c.includes('✅') || c.includes('WIN'));
    }

    const dimensions: ScorecardDimension[] = dimNames.map((name, i) => {
        const results: Record<string, boolean> = {};
        for (const v of vendors) {
            results[v] = vendorResults[v]?.[i] ?? false;
        }
        return { name, results };
    });

    // Summary line like "MongoDB wins 3/6 dimensions"
    const summaryMatch = section.match(/(\w[\w\s]*?)\s+wins?\s+(\d+\/\d+)\s+dimensions?/i);
    const summary = summaryMatch ? `${summaryMatch[1].trim()} wins ${summaryMatch[2]} dimensions` : '';

    return { vendors, dimensions, summary };
}

export function extractDimensionBreakdown(content: string): DimensionDetail[] {
    const section = getSection(content, 'DIMENSION BREAKDOWN');
    if (!section) return [];

    const items: DimensionDetail[] = [];
    // Split by dimension entries (⭐ or •)
    const parts = section.split(/\n\s*(?=[⭐•])/);

    for (const part of parts) {
        const lines = part.split('\n').map(l => l.trim()).filter(Boolean);
        if (lines.length === 0) continue;

        const isPriority = lines[0].includes('⭐');
        const nameMatch = lines[0].match(/[⭐•]\s*(.+?)(?:\s*\(.*\))?$/);
        const name = nameMatch ? nameMatch[1].trim() : lines[0];

        const winnerMatch = lines.find(l => /winner:/i.test(l));
        const winner = winnerMatch ? winnerMatch.replace(/.*winner:\s*/i, '').trim() : '';

        const whyMatch = lines.find(l => /why:/i.test(l));
        const why = whyMatch ? whyMatch.replace(/.*why:\s*/i, '').trim() : '';

        if (name) items.push({ name, winner, why, isPriority });
    }

    return items;
}

export function extractTradeoffs(content: string): TradeoffsData | null {
    const section = getSection(content, 'TRADEOFFS');
    if (!section) return null;

    const vendorMatch = section.match(/BY CHOOSING\s+(.+?),/i);
    const chosenVendor = vendorMatch ? vendorMatch[1].trim() : '';

    const benefits: string[] = [];
    const sacrifices: string[] = [];

    const lines = section.split('\n');
    let mode: 'benefits' | 'sacrifices' | null = null;

    for (const line of lines) {
        if (/BY CHOOSING/i.test(line)) { mode = 'benefits'; continue; }
        if (/BUT YOU MAY/i.test(line)) { mode = 'sacrifices'; continue; }

        const trimmed = line.trim();
        if (!trimmed) continue;

        if (mode === 'benefits' && trimmed.startsWith('✅')) {
            benefits.push(trimmed.replace(/^✅\s*/, ''));
        } else if (mode === 'sacrifices' && trimmed.startsWith('⚠️')) {
            sacrifices.push(trimmed.replace(/^⚠️\s*/, ''));
        }
    }

    return { chosenVendor, benefits, sacrifices };
}

export function extractRunnerUp(content: string): RunnerUpData | null {
    const section = getSection(content, 'RUNNER UP');
    if (!section) return null;

    const lines = section.split('\n').map(l => l.trim()).filter(Boolean);
    const firstLine = lines[0] || '';
    const dashIdx = firstLine.indexOf('—');

    const vendor = dashIdx > -1 ? firstLine.slice(0, dashIdx).trim() : firstLine;
    const reason = dashIdx > -1 ? firstLine.slice(dashIdx + 1).trim() : '';

    const swingMatch = section.match(/SWING FACTOR:\s*(.+)/i);
    const swingFactor = swingMatch ? swingMatch[1].trim() : '';

    return { vendor, reason, swingFactor };
}

export function extractQuestions(content: string): string[] {
    const section = getSection(content, 'QUESTIONS TO ASK');
    if (!section) return [];

    return section
        .split('\n')
        .map(l => l.trim())
        .filter(l => /^\d+\.\s*"/.test(l) || /^\d+\.\s/.test(l))
        .map(l => l.replace(/^\d+\.\s*/, '').replace(/^"|"$/g, '').trim());
}

export function extractConfidenceBreakdown(content: string): ConfidenceData | null {
    const section = getSection(content, 'CONFIDENCE BREAKDOWN');
    if (!section) return null;

    const overallMatch = section.match(/Overall:\s*(\d+)%\s*\((\w+)\)/i);
    const dimMatch = section.match(/Dimensions Won:\s*(\S+)/i);
    const prioMatch = section.match(/Priority Dimension Won:\s*(\w+)/i);
    const domMatch = section.match(/Dominance:\s*(\S+)/i);

    return {
        overall: overallMatch ? parseInt(overallMatch[1]) : 0,
        label: overallMatch ? overallMatch[2] : '',
        dimensionsWon: dimMatch ? dimMatch[1] : '',
        priorityWon: prioMatch ? prioMatch[1].toLowerCase() === 'yes' : false,
        dominance: domMatch ? domMatch[1] : '',
    };
}

export function extractBuyerNextSteps(content: string): string[] {
    const section = getSection(content, 'RECOMMENDED NEXT STEPS') || getSection(content, 'NEXT STEPS');
    if (!section) return [];

    return section
        .split('\n')
        .map(l => l.trim())
        .filter(l => /^\d+\.\s/.test(l))
        .map(l => l.replace(/^\d+\.\s*/, '').trim());
}

// ─── Seller Extractors ─────────────────────────────────────────

export function extractWinProbability(content: string): number {
    const m = content.match(/WIN PROBABILITY:\s*(\d+)%/i);
    return m ? parseInt(m[1]) : 0;
}

export function extractDimensionsWon(content: string): string {
    const m = content.match(/You won (\d+\/\d+ dimensions)/i);
    return m ? m[1] : '';
}

export function extractAdvantages(content: string): AdvantageItem[] {
    const section = getSection(content, 'YOUR ADVANTAGES');
    if (!section) return [];

    const items: AdvantageItem[] = [];
    const parts = section.split(/\n\s*(?=\d+\.)/);

    for (const part of parts) {
        const lines = part.split('\n').map(l => l.trim()).filter(Boolean);
        if (lines.length === 0) continue;

        const titleLine = lines[0];
        const isPriority = titleLine.includes('⭐');
        const titleMatch = titleLine.match(/\d+\.\s*(.+?)(?:\s*⭐.*)?$/);
        const title = titleMatch ? titleMatch[1].replace(/⭐.*/, '').trim() : titleLine;

        const quoteLine = lines.find(l => l.startsWith('"'));
        const quote = quoteLine ? quoteLine.replace(/^"|"$/g, '').trim() : '';

        const tipLine = lines.find(l => l.startsWith('→'));
        const tip = tipLine ? tipLine.replace(/^→\s*/, '').trim() : '';

        if (title) items.push({ title, quote, tip, isPriority });
    }

    return items;
}

export function extractVulnerabilities(content: string): VulnerabilityItem[] {
    const section = getSection(content, 'YOUR VULNERABILITIES');
    if (!section) return [];

    const items: VulnerabilityItem[] = [];
    const parts = section.split(/\n\s*(?=\d+\.\s*⚠️)/);

    for (const part of parts) {
        const lines = part.split('\n').map(l => l.trim()).filter(Boolean);
        if (lines.length === 0) continue;

        const titleMatch = lines[0].match(/\d+\.\s*⚠️\s*(.+)/);
        const title = titleMatch ? titleMatch[1].trim() : lines[0];

        const compLine = lines.find(l => /wins here/i.test(l));
        const competitor = compLine ? (compLine.match(/^(\w+)/)?.[1] || '') : '';
        const quote = compLine ? (compLine.match(/"(.+)"/)?.[1] || '') : '';

        const tipLine = lines.find(l => l.startsWith('→'));
        const tip = tipLine ? tipLine.replace(/^→\s*/, '').trim() : '';

        if (title) items.push({ title, competitor, quote, tip });
    }

    return items;
}

export function extractLandmines(content: string): LandmineData | null {
    const section = getSection(content, 'LANDMINES');
    if (!section) return null;

    const theySay: string[] = [];
    let youSay = '';

    const lines = section.split('\n');
    let mode: 'they' | 'you' | null = null;

    for (const line of lines) {
        const t = line.trim();
        if (/IF .+ SAYS:/i.test(t)) { mode = 'they'; continue; }
        if (/YOU SAY:/i.test(t)) { mode = 'you'; continue; }

        if (mode === 'they' && t.startsWith('"')) {
            theySay.push(t.replace(/^"|"$/g, '').trim());
        }
        if (mode === 'you' && t) {
            youSay += (youSay ? '\n' : '') + t.replace(/^"|"$/g, '');
        }
    }

    return { theySay, youSay: youSay.trim() };
}

export function extractTalkTrack(content: string): TalkTrackData | null {
    const section = getSection(content, 'TALK TRACK');
    if (!section) return null;

    let opening = '';
    const keyPoints: string[] = [];
    let close = '';

    const lines = section.split('\n');
    let mode: 'opening' | 'key' | 'close' | null = null;

    for (const line of lines) {
        const t = line.trim();
        if (/OPENING:/i.test(t)) { mode = 'opening'; continue; }
        if (/KEY POINTS/i.test(t)) { mode = 'key'; continue; }
        if (/CLOSE:/i.test(t)) { mode = 'close'; continue; }

        if (mode === 'opening' && t) opening += (opening ? ' ' : '') + t.replace(/^"|"$/g, '');
        if (mode === 'key' && /^\d+\./.test(t)) keyPoints.push(t.replace(/^\d+\.\s*/, ''));
        if (mode === 'close' && t) close += (close ? ' ' : '') + t.replace(/^"|"$/g, '');
    }

    return { opening: opening.trim(), keyPoints, close: close.trim() };
}

export function extractDoNotSay(content: string): string[] {
    const section = getSection(content, 'DO NOT SAY');
    if (!section) return [];

    return section
        .split('\n')
        .map(l => l.trim())
        .filter(l => l.startsWith('•') || l.startsWith("Don't"))
        .map(l => cleanLine(l));
}

export function extractObjectionHandling(content: string): ObjectionItem[] {
    const section = getSection(content, 'OBJECTION HANDLING');
    if (!section) return [];

    const items: ObjectionItem[] = [];
    const parts = section.split(/\n\s*(?=\d+\.\s*Objection:)/);

    for (const part of parts) {
        const objMatch = part.match(/Objection:\s*"?(.+?)"?\s*Suggested response:\s*"?(.+?)"?\s*$/is);
        if (objMatch) {
            items.push({ objection: objMatch[1].trim(), response: objMatch[2].trim() });
        }
    }

    return items;
}

export function extractSellerNextSteps(content: string): NextStepGroup[] {
    const section = getSection(content, 'NEXT STEPS');
    if (!section) return [];

    const groups: NextStepGroup[] = [];
    let currentPhase = '';
    let currentItems: string[] = [];

    for (const line of section.split('\n')) {
        const t = line.trim();
        if (/^[A-Z\s]+:$/.test(t)) {
            if (currentPhase && currentItems.length) {
                groups.push({ phase: currentPhase, items: currentItems });
            }
            currentPhase = t.replace(/:$/, '').trim();
            currentItems = [];
        } else if (t.startsWith('[ ]') || t.startsWith('[x]')) {
            currentItems.push(t.replace(/^\[.\]\s*/, '').trim());
        }
    }

    if (currentPhase && currentItems.length) {
        groups.push({ phase: currentPhase, items: currentItems });
    }

    return groups;
}

export function extractDealSummary(content: string): Record<string, string> {
    const section = getSection(content, 'DEAL SUMMARY');
    if (!section) return {};

    const data: Record<string, string> = {};
    for (const line of section.split('\n')) {
        const m = line.match(/^\s*(.+?)\s*:\s*(.+)/);
        if (m) data[m[1].trim()] = m[2].trim();
    }
    return data;
}

// ─── Analyst Extractors ────────────────────────────────────────

export function extractAnalystSummary(content: string): AnalystSummary | null {
    const section = getSection(content, 'EXECUTIVE SUMMARY');
    if (!section) return null;

    // Description lines before DIMENSION WINS
    const descLines = section.split('\n').filter(l => {
        const t = l.trim();
        return t && !t.includes('DIMENSION WINS') && !t.includes('████') && !t.includes('░░░') && !/^\w+\s+[█░]+/.test(t);
    });
    const description = descLines.map(l => l.trim()).join(' ').trim();

    // Parse dimension win bars: "MongoDB              ████░░░ 4/7"
    const dimensionWins: { vendor: string; wins: number; total: number }[] = [];
    const winLines = section.match(/^\s*(\w[\w\s]*?)\s+[█░]+\s+(\d+)\/(\d+)/gm);
    if (winLines) {
        for (const wl of winLines) {
            const m = wl.match(/^\s*(.+?)\s+[█░]+\s+(\d+)\/(\d+)/);
            if (m) {
                dimensionWins.push({
                    vendor: m[1].trim(),
                    wins: parseInt(m[2]),
                    total: parseInt(m[3]),
                });
            }
        }
    }

    return { description, dimensionWins };
}

export function extractAnalystMatrix(content: string): ScorecardData | null {
    const section = getSection(content, 'COMPARISON MATRIX');
    if (!section) return null;

    const lines = section.split('\n').map(l => l.trim()).filter(Boolean);

    // Find header line with dimension names
    const headerLine = lines.find(l => /Dimension/i.test(l));
    if (!headerLine) return null;

    const headerParts = headerLine.split(/\s{2,}/).map(s => s.trim()).filter(Boolean);
    const vendors = headerParts.slice(1); // first is "Dimension"

    // Parse data rows
    const dimensions: ScorecardDimension[] = [];
    for (const line of lines) {
        if (/^─+$/.test(line) || /Dimension/i.test(line) || /TOTAL/i.test(line)) continue;
        const parts = line.split(/\s{2,}/).map(s => s.trim()).filter(Boolean);
        if (parts.length < 2) continue;

        const dimName = parts[0];
        const results: Record<string, boolean> = {};
        vendors.forEach((v, i) => {
            const cell = parts[i + 1] || '';
            results[v] = cell.includes('✅') || cell.includes('WINS') || cell.includes('WIN');
        });
        dimensions.push({ name: dimName, results });
    }

    if (dimensions.length === 0) return null;

    // Grab total wins line
    const totalLine = lines.find(l => /TOTAL WINS/i.test(l));
    const summary = totalLine || '';

    return { vendors, dimensions, summary };
}

export function extractDimensionAnalysis(content: string): DimensionAnalysis[] {
    const section = getSection(content, 'DIMENSION ANALYSIS');
    if (!section) return [];

    const items: DimensionAnalysis[] = [];
    const parts = section.split(/\n\s*(?=▸)/);

    for (const part of parts) {
        const lines = part.split('\n').map(l => l.trim()).filter(Boolean);
        if (lines.length === 0) continue;

        const dimMatch = lines[0].match(/▸\s*(.+)/);
        const dimension = dimMatch ? dimMatch[1].trim() : '';

        const leaderLine = lines.find(l => /Leader:/i.test(l));
        const leader = leaderLine ? leaderLine.replace(/.*Leader:\s*/i, '').trim() : '';

        const analysisLine = lines.find(l => /Analysis:/i.test(l));
        const analysis = analysisLine ? analysisLine.replace(/.*Analysis:\s*/i, '').trim() : '';

        if (dimension) items.push({ dimension, leader, analysis });
    }

    return items;
}

export function extractVendorProfiles(content: string): VendorProfile[] {
    const section = getSection(content, /STRENGTHS.*WEAKNESSES|STRENGTHS & WEAKNESSES/);
    if (!section) return [];

    const profiles: VendorProfile[] = [];
    // Split by vendor blocks: "┌─ VENDORNAME"
    const blocks = section.split(/\n\s*┌─\s*/);

    for (const block of blocks) {
        const lines = block.split('\n').map(l => l.replace(/[│└┌─]+/g, '').trim()).filter(Boolean);
        if (lines.length === 0) continue;

        const vendor = lines[0].trim();
        if (!vendor) continue;

        const strengths: string[] = [];
        const weaknesses: string[] = [];
        let mode: 'str' | 'weak' | null = null;

        for (const line of lines.slice(1)) {
            if (/Strengths:/i.test(line)) { mode = 'str'; continue; }
            if (/Weaknesses:/i.test(line)) { mode = 'weak'; continue; }

            const clean = line.replace(/^[✅⚠️]\s*/, '').trim();
            if (!clean || clean === '(none in this comparison)') continue;

            if (mode === 'str' && line.includes('✅')) strengths.push(clean);
            else if (mode === 'weak' && line.includes('⚠️')) weaknesses.push(clean);
        }

        profiles.push({ vendor, strengths, weaknesses });
    }

    return profiles;
}

export function extractBestFitScenarios(content: string): BestFitScenario[] {
    const section = getSection(content, 'BEST FIT SCENARIOS');
    if (!section) return [];

    const scenarios: BestFitScenario[] = [];
    const parts = section.split(/\n\s*(?=CHOOSE\s)/);

    for (const part of parts) {
        const lines = part.split('\n').map(l => l.trim()).filter(Boolean);
        if (lines.length === 0) continue;

        const vendorMatch = lines[0].match(/CHOOSE\s+(.+?)\s+IF:/i);
        if (!vendorMatch) continue;

        const vendor = vendorMatch[1].trim();
        const conditions = lines.slice(1)
            .map(l => cleanLine(l))
            .filter(Boolean);

        scenarios.push({ vendor, conditions });
    }

    return scenarios;
}

export function extractAnalystTradeoffs(content: string): AnalystTradeoff[] {
    const section = getSection(content, 'KEY TRADEOFFS');
    if (!section) return [];

    const tradeoffs: AnalystTradeoff[] = [];
    const blocks = section.split(/\n\s*(?=\w.*vs\s)/i);

    for (const block of blocks) {
        const lines = block.split('\n').map(l => l.trim()).filter(Boolean);
        if (lines.length === 0) continue;

        const titleMatch = lines[0].match(/(.+\s+vs\s+.+):/i);
        const title = titleMatch ? titleMatch[1].trim() : lines[0].replace(/:$/, '');

        const bodyLines = lines.slice(1).map(l => l.replace(/^→\s*/, '').trim()).filter(Boolean);
        tradeoffs.push({ title, lines: bodyLines });
    }

    return tradeoffs;
}

export function extractDataQuality(content: string): DataQuality | null {
    const section = getSection(content, 'DATA QUALITY');
    if (!section) return null;

    const scoreMatch = section.match(/ANALYSIS QUALITY:\s*(.+)/i);
    const score = scoreMatch ? scoreMatch[1].trim() : '';

    const details: string[] = [];
    const caveats: string[] = [];
    let mode: 'details' | 'caveats' | null = null;

    for (const line of section.split('\n')) {
        const t = line.trim();
        if (/Based on:/i.test(t)) { mode = 'details'; continue; }
        if (/CAVEATS:/i.test(t)) { mode = 'caveats'; continue; }

        if (mode === 'details' && t.startsWith('•')) details.push(cleanLine(t));
        if (mode === 'caveats' && t.startsWith('•')) caveats.push(cleanLine(t));
    }

    return { score, details, caveats };
}

export function extractMethodology(content: string): MethodologyStep[] {
    const section = getSection(content, 'METHODOLOGY');
    if (!section) return [];

    const steps: MethodologyStep[] = [];
    const parts = section.split(/\n\s*(?=\d+\.\s)/);

    for (const part of parts) {
        const lines = part.split('\n').map(l => l.trim()).filter(Boolean);
        if (lines.length === 0) continue;

        const nameMatch = lines[0].match(/\d+\.\s*(.+)/);
        if (!nameMatch) continue;

        const name = nameMatch[1].trim();
        const description = lines.slice(1).map(l => l.replace(/^Sources?:\s*/i, 'Sources: ')).join(' ').trim();

        steps.push({ name, description });
    }

    return steps;
}
