import { useQuery } from '@tanstack/react-query';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export function useAllVendors() {
    return useQuery({
        queryKey: ['vendors', 'all'],
        queryFn: async () => {
            const [database, cloud, crm] = await Promise.all([
                fetch(`${API_BASE_URL}/api/vendors/database/enriched`).then(r => r.json()).catch(() => []),
                fetch(`${API_BASE_URL}/api/vendors/cloud/enriched`).then(r => r.json()).catch(() => []),
                fetch(`${API_BASE_URL}/api/vendors/crm/enriched`).then(r => r.json()).catch(() => []),
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
            return fetch(`${API_BASE_URL}/api/sessions?${params}`).then(r => r.json());
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
            return fetch(`${API_BASE_URL}/api/sessions/trends?${params}`).then(r => r.json());
        },
    });
}

export function useReport(reportId: string | undefined) {
    return useQuery({
        queryKey: ['report', reportId],
        queryFn: () => fetch(`${API_BASE_URL}/api/reports/${reportId}`).then(r => r.json()),
        enabled: !!reportId,
    });
}