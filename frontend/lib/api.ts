export const API = process.env.NEXT_PUBLIC_API_URL ?? (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');
export type Subject = { name: string; scope: string; page_number?: number | null; evidence?: string | null };
export type Source = { id: number; url: string; title: string; demo: boolean; page_number?: number | null; content_hash: string; fetched_at: string };
export type Version = { id: number; version: number; revision: string; status: string; start_date: string | null; end_date: string | null; confidence: number; created_at: string; subjects: Subject[]; source: Source };
export type Exam = { id: number; school_id: string; school_name: string; school_short_name: string; city: string; grade: number; academic_year: number; semester: number; number: number; start_date: string | null; end_date: string | null; subjects: Subject[]; confidence: number; updated_at: string; sources: Source[]; versions: Version[]; status: string; demo: boolean };
export type Page<T> = { items: T[]; total: number; demo?: boolean };
export type Metadata = { cities: string[]; grades: number[]; academic_years: number[]; subjects: string[]; statistics: { schools: number; exams: number }; current_academic_year: number };
export type School = { id: string; name: string; short_name: string; city: string; website: string; domains: string[]; demo: boolean; crawl_enabled: boolean; crawler_status: string; last_crawled_at: string | null; last_success_at: string | null };
export type Job = { id: number; school_id: string; school_name: string; status: string; pages_checked: number; documents: number; new_exams: number; error: string | null; created_at: string; started_at: string | null; completed_at: string | null; errors: { url: string; message: string }[] };
export type Review = { id: number; exam: Exam; version: Version };
export type Summary = { schools: number; enabled_schools: number; needs_review: number; jobs: Record<string, number>; worker: { online: boolean; heartbeat_at: string | null; current_job_id: number | null } };
export type DocumentRecord = { id: number; source_id: number; school_name: string; status: string; source: Source; excerpt: string; truncated: boolean };
export type ParsedDocument = { source: Source; text: string; pages: { page: number | null; text: string; sheet?: string }[]; truncated: boolean; status: string };
export type Audit = { id: number; entity: string; entity_id: string; action: string; before: Record<string, unknown> | null; after: Record<string, unknown> | null; created_at: string };

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

export async function request<T>(path: string, token?: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  init.signal?.addEventListener('abort', cancel, { once: true });
  if (init.signal?.aborted) cancel();
  const timer = setTimeout(cancel, 20000);
  const headers = new Headers(init.headers);
  if (init.body) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', 'Bearer ' + token);
  try {
    const response = await fetch(API + path, { ...init, headers, signal: controller.signal, cache: 'no-store' });
    if (!response.ok) {
      const messages: Record<number, string> = { 401: '管理權杖無效，請重新登入。', 403: '沒有執行此操作的權限。', 404: '資料不存在，請重新載入或查看原公告。', 409: '資料已變更或操作不符合目前狀態，請重新載入後再試。', 422: '資料格式不符，請檢查日期、科目、學校網域與必填欄位。', 502: '情報服務暫時無法連線，請稍後重試。', 503: '情報服務尚未就緒，請稍後重試。' };
      throw new ApiError(response.status, messages[response.status] || '操作未成功，請稍後重試。');
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiError || init.signal?.aborted) throw error;
    throw new ApiError(0, controller.signal.aborted ? '連線逾時，請稍後重試。' : '無法取得資料，請檢查連線後重試。');
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener('abort', cancel);
  }
}
