import { useQuery } from '@tanstack/react-query';
import { authFetch } from '../lib/api';

// Callers cast to their own EnrichedVendor shape; keep as any[] for compat
// but guarantee at runtime we always return an array.
async function fetchArray(path: string): Promise<any[]> {
    try {
        const res = await authFetch(path);
        if (!res.ok) return [];
        const data = await res.json();
        return Array.isArray(data) ? data : [];
    } catch {
        return [];
    }
}

export function useAllVendors() {
    return useQuery({
        queryKey: ['vendors', 'all'],
        queryFn: async () => {
            const [database, cloud, crm] = await Promise.all([
                fetchArray(`/api/vendors/database/enriched`),
                fetchArray(`/api/vendors/cloud/enriched`),
                fetchArray(`/api/vendors/crm/enriched`),
            ]);
            return { database, cloud, crm };
        },
    });
}

export function useSessions(days = 30, limit = 20, offset = 0, mode = '', vertical = '') {
    return useQuery({
        queryKey: ['sessions', days, limit, offset, mode, vertical],
        queryFn: () => {
            const params = new URLSearchParams();
            if (mode) params.set('mode', mode);
            if (vertical) params.set('vertical', vertical);
            params.set('days', days.toString());
            params.set('limit', limit.toString());
            params.set('offset', offset.toString());
            return authFetch(`/api/sessions?${params}`).then(r => r.json());
        },
    });
}

export function useSessionTrends(days = 30, mode = '', vertical = '') {
    return useQuery({
        queryKey: ['trends', days, mode, vertical],
        queryFn: () => {
            const params = new URLSearchParams();
            if (mode) params.set('mode', mode);
            if (vertical) params.set('vertical', vertical);
            params.set('days', days.toString());
            return authFetch(`/api/sessions/trends?${params}`).then(r => r.json());
        },
    });
}

export function useReport(reportId: string | undefined) {
    return useQuery({
        queryKey: ['report', reportId],
        queryFn: () => authFetch(`/api/reports/${reportId}`).then(r => r.json()),
        enabled: !!reportId,
    });
}
