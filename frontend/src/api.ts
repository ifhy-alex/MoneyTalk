// Cliente HTTP tipado. Los montos llegan como string (Decimal) para no perder precisión.

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    ...init,
    headers:
      init?.body instanceof FormData
        ? init.headers
        : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = (await resp.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.status === 204 ? (undefined as T) : ((await resp.json()) as T);
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
    }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  del: (path: string) => request<void>(path, { method: "DELETE" }),
};

export function qs(params: Record<string, string | number | boolean | undefined | null>) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return entries.length ? `?${new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))}` : "";
}

// --- Tipos de dominio ---

export type Currency = "CRC" | "USD";
export type CategoryStatus = "uncategorized" | "suggested" | "confirmed";
export type MatchType = "exact" | "contains" | "regex";

export interface Category {
  id: number;
  name: string;
  parent_id: number | null;
  kind: "expense" | "income" | "transfer";
  is_subscription: boolean;
}

export interface Transaction {
  id: number;
  account_id: number;
  account_label: string;
  txn_date: string;
  occurred_at: string | null;
  amount: string;
  currency: Currency;
  merchant_raw: string;
  merchant_normalized: string;
  category_id: number | null;
  category_name: string | null;
  category_status: CategoryStatus;
  category_source: "rule" | "ai" | "manual" | null;
  ai_reason: string | null;
  notes: string | null;
  sources: { raw_document_id: number; source_type: string; match_confidence: string }[];
}

export interface Rule {
  id: number;
  match_type: MatchType;
  pattern: string;
  category_id: number;
  category_name: string;
  priority: number;
  is_active: boolean;
}

export interface RuleSuggestion {
  match_type: MatchType;
  pattern: string;
  category_id: number;
  would_affect: number;
}

export interface IngestResult {
  documents_new: number;
  documents_skipped: number;
  documents_failed: number;
  transactions_created: number;
  transactions_merged: number;
  errors: string[];
}

export interface RawDocument {
  id: number;
  source_type: "email" | "pdf_statement";
  subject: string | null;
  received_at: string | null;
  parser_name: string | null;
  parser_version: string | null;
  status: "pending" | "parsed" | "failed" | "ignored";
  error: string | null;
  created_at: string;
}
