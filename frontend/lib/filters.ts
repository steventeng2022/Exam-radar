export type Filters = { q: string; city: string; school_id: string; grade: string; academic_year: string; semester: string; number: string; subject: string };
export const PAGE_SIZE = 24;
export function initialFilters(search: string, compare: boolean): Filters {
  const params = new URLSearchParams(search);
  const valid = (key: string, values: string[], fallback = '') => values.includes(params.get(key) || '') ? params.get(key)! : fallback;
  return { q: (params.get('q') || '').slice(0, 200), city: (params.get('city') || '').slice(0, 40), school_id: (params.get('school_id') || '').slice(0, 80), grade: valid('grade', ['7','8','9','10','11','12'], compare ? '11' : ''), academic_year: /^\d{3}$/.test(params.get('academic_year') || '') ? params.get('academic_year')! : '', semester: valid('semester', ['1','2'], compare ? '1' : ''), number: valid('number', ['1','2','3'], compare ? '1' : ''), subject: (params.get('subject') || (compare ? '數學A' : '')).slice(0, 50) };
}
export function filterParams(filters: Filters, page = 0, pagination = true): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value.trim()) params.set(key, value.trim());
  if (pagination) { params.set('limit', String(PAGE_SIZE)); params.set('offset', String(Math.max(0, page) * PAGE_SIZE)); }
  return params.toString();
}
export function gradeLabel(grade: number): string {
  return ({ 7: '國一', 8: '國二', 9: '國三', 10: '高一', 11: '高二', 12: '高三' } as Record<number, string>)[grade] || String(grade) + ' 年級';
}
export function statusLabel(status: string): string {
  return ({ queued: '待執行', running: '執行中', completed: '已完成', warning: '部分失敗', failed: '失敗', cancelled: '已取消', review: '待審核', approved: '已發布', published: '已發布', rejected: '已拒絕', needs_manual: '需人工整理', idle: '尚未執行', healthy: '正常', edit: '編輯', approve: '批准', reject: '拒絕', settings: '設定', import: '匯入', enqueue: '排入', retry: '重試', cancel: '取消', manual_extract: '人工整理', recover: '恢復', schedule: '排程' } as Record<string, string>)[status] || status;
}
export function formatTime(value: string | null | undefined): string {
  if (!value) return '尚無紀錄';
  return new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : value + 'Z').toLocaleString('zh-TW', { timeZone: 'Asia/Taipei', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
