import { supabase } from './supabase';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

/**
 * Fetch wrapper for /api/* calls that attaches the Supabase Bearer token
 * when a session exists. Callers that require auth should check
 * useAuth().session themselves before invoking mutating actions.
 */
export async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const { data: { session } } = await supabase.auth.getSession();

  const { headers: extraHeaders, ...rest } = options;

  return fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      'Content-Type': 'application/json',
      ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...(extraHeaders as Record<string, string> ?? {}),
    },
  });
}
