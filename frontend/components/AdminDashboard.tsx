'use client';
import { useEffect, useState } from 'react';
import { request, type Audit, type DocumentRecord, type Job, type Page, type Review, type School, type Summary } from '../lib/api';
import { formatTime, statusLabel } from '../lib/filters';
import ReviewCard from './ReviewCard';
import DocumentDialog from './DocumentDialog';
import SchoolManager from './SchoolManager';
import { SourceLink } from './ExamDialog';
type Tab = 'crawls' | 'review' | 'schools' | 'documents' | 'audit';
const tabs: [Tab, string][] = [['crawls', '爬取工作'], ['review', '待審核'], ['schools', '學校名冊'], ['documents', '文件原文'], ['audit', '操作紀錄']];
export default function AdminDashboard() {
  const [draftToken, setDraftToken] = useState('');
  const [token, setToken] = useState('');
  const [tab, setTab] = useState<Tab>('crawls');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [schools, setSchools] = useState<School[]>([]);
  const [jobs, setJobs] = useState<Page<Job>>({ items: [], total: 0 });
  const [reviews, setReviews] = useState<Page<Review>>({ items: [], total: 0 });
  const [documents, setDocuments] = useState<Page<DocumentRecord>>({ items: [], total: 0 });
  const [audits, setAudits] = useState<Page<Audit>>({ items: [], total: 0 });
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState('');
  const [schoolId, setSchoolId] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [sourceId, setSourceId] = useState<number | null>(null);
  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setLoading(true); setError('');
    const init = { signal: controller.signal };
    async function load() {
      const [stats, registry] = await Promise.all([request<Summary>('/api/admin/summary', token, init), request<Page<School>>('/api/schools', token, init)]);
      if (controller.signal.aborted) return;
      setSummary(stats); setSchools(registry.items);
      const query = `?limit=20&offset=${page * 20}${status ? '&status=' + encodeURIComponent(status) : ''}`;
      if (tab === 'crawls') setJobs(await request<Page<Job>>('/api/admin/crawls' + query, token, init));
      if (tab === 'review') setReviews(await request<Page<Review>>('/api/admin/review' + query, token, init));
      if (tab === 'documents') setDocuments(await request<Page<DocumentRecord>>('/api/admin/documents' + query, token, init));
      if (tab === 'audit') setAudits(await request<Page<Audit>>('/api/admin/audit' + query, token, init));
    }
    load().catch(error => { if (!controller.signal.aborted) setError(error.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [token, tab, page, status, refresh]);
  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    const timer = setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      request<Summary>('/api/admin/summary', token, { signal: controller.signal }).then(data => { if (!controller.signal.aborted) setSummary(data); }).catch(() => {});
      if (tab === 'crawls') request<Page<Job>>(`/api/admin/crawls?limit=20&offset=${page * 20}${status ? '&status=' + encodeURIComponent(status) : ''}`, token, { signal: controller.signal }).then(data => { if (!controller.signal.aborted) setJobs(data); }).catch(() => {});
    }, 15000);
    return () => { clearInterval(timer); controller.abort(); };
  }, [token, tab, page, status]);
  const reload = () => setRefresh(value => value + 1);
  async function mutate(path: string, body: unknown, message: string): Promise<boolean> {
    setBusy(true); setError(''); setNotice('');
    try { await request(path, token, { method: 'POST', body: JSON.stringify(body) }); setNotice(message); reload(); return true; }
    catch (error) { setError((error as Error).message); return false; }
    finally { setBusy(false); }
  }
  const total = tab === 'crawls' ? jobs.total : tab === 'review' ? reviews.total : tab === 'documents' ? documents.total : audits.total;
  useEffect(() => { if (!loading && tab !== 'schools' && page > 0 && page * 20 >= total) setPage(Math.max(0, Math.ceil(total / 20) - 1)); }, [total, page, loading, tab]);
  function logout() { setToken(''); setSummary(null); setSchools([]); setJobs({items:[],total:0}); setReviews({items:[],total:0}); setDocuments({items:[],total:0}); setAudits({items:[],total:0}); setSourceId(null); setError(''); setNotice(''); setPage(0); }
  return <section className="info-page dashboard"><div className="eyebrow">CONTROL CENTER</div><h1>管理<span className="accent">控制台</span></h1><p className="lead">匯入學校 → 啟用爬取 → 核對來源 → 審核發布。</p>{!token ? <form className="admin-login" onSubmit={event => { event.preventDefault(); setToken(draftToken.trim()); setDraftToken(''); }}><label htmlFor="token">管理員 API 權杖</label><div><input id="token" required type="password" value={draftToken} onChange={event => setDraftToken(event.target.value)} placeholder="輸入管理權杖" autoComplete="off" /><button className="primary" disabled={!draftToken.trim()}>開啟控制台</button></div><small>權杖只保留於本頁記憶體。重新整理或登出後需再次輸入。</small></form> : <><div className="actions"><button className="secondary" disabled={loading || busy} onClick={reload}>重新載入</button><button className="secondary" disabled={busy} onClick={logout}>登出</button></div>{summary && <><div className="dashboard-stats"><div><strong>{summary.enabled_schools}</strong><span>啟用學校 / {summary.schools}</span></div><div><strong>{summary.needs_review}</strong><span>待審核版本</span></div><div><strong>{summary.jobs.queued || 0}</strong><span>等候爬取</span></div><div><strong>{summary.worker.online ? '在線' : '離線'}</strong><span>爬蟲 · {formatTime(summary.worker.heartbeat_at)}</span></div></div>{!summary.worker.online && <p className="demo-notice">爬蟲目前離線，已排入的工作會等候處理。請確認 VPS 上的 crawler 服務已啟動。</p>}</>}<div className="dashboard-tabs" aria-label="管理功能">{tabs.map(([key, label]) => <button key={key} disabled={busy} aria-pressed={tab === key} className={tab === key ? 'selected' : ''} onClick={() => { setTab(key); setPage(0); setStatus(''); setNotice(''); }}>{label}{key === 'review' && summary ? ` (${summary.needs_review})` : ''}</button>)}</div>{error && <p className="demo-notice" role="alert">{error} <button className="text-link" onClick={reload}>重新載入</button></p>}{notice && <p className="success-notice" role="status">{notice}</p>}{loading ? <p role="status">讀取控制台…</p> : <>{tab === 'crawls' && <><div className="admin-login"><label htmlFor="enqueue-school">新增爬取工作</label><div><select id="enqueue-school" value={schoolId} onChange={event => setSchoolId(event.target.value)}><option value="">選擇已啟用的正式學校</option>{schools.filter(s => s.crawl_enabled && !s.demo).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select><button className="primary" disabled={!schoolId || busy} onClick={() => mutate(`/api/admin/crawl/${schoolId}`, {}, '工作已排入；重複操作會使用既有工作。')}>排入爬取</button></div></div><label className="filter-label">工作狀態<select value={status} onChange={event => { setStatus(event.target.value); setPage(0); }}><option value="">全部</option>{['queued','running','completed','warning','failed','cancelled'].map(s => <option key={s} value={s}>{statusLabel(s)}</option>)}</select></label><div className="table-scroll"><table><thead><tr><th>工作 / 學校</th><th>狀態</th><th>頁面 / 文件 / 新版本</th><th>時間 / 錯誤</th><th>操作</th></tr></thead><tbody>{jobs.items.map(job => <tr key={job.id}><td>#{job.id} {job.school_name}</td><td>{statusLabel(job.status)}</td><td>{job.pages_checked} / {job.documents} / {job.new_exams}</td><td>{formatTime(job.completed_at || job.started_at || job.created_at)}{job.error && <small>{job.error}</small>}{job.errors.length > 0 && <details><summary>{job.errors.length} 筆錯誤</summary>{job.errors.map((error, index) => <p className="error-detail" key={index}>{error.url}<br />{error.message}</p>)}</details>}</td><td>{['queued','running'].includes(job.status) && <button className="secondary" disabled={busy} onClick={() => mutate(`/api/admin/crawls/${job.id}/cancel`, {}, '工作已取消；進行中的請求完成後停止。')}>取消</button>}{['warning','failed','cancelled'].includes(job.status) && <button className="secondary" disabled={busy} onClick={() => mutate(`/api/admin/crawls/${job.id}/retry`, {}, '已建立重試工作，原工作紀錄保留。')}>重試</button>}</td></tr>)}</tbody></table></div></>}{tab === 'review' && reviews.items.map(review => <ReviewCard key={`${review.id}-${review.version.revision}`} review={review} token={token} refresh={reload} document={setSourceId} />)}{tab === 'schools' && <SchoolManager schools={schools} busy={busy} mutate={mutate} />}{tab === 'documents' && <><p className="muted">未成功建立段考資料的文件，可在此查看原文；可依原公告人工建立待審核版本。</p><label className="filter-label">文件狀態<select value={status} onChange={event => { setStatus(event.target.value); setPage(0); }}><option value="">全部</option>{['needs_manual','review','published','rejected'].map(s => <option value={s} key={s}>{statusLabel(s)}</option>)}</select></label>{documents.items.map(doc => <article className="review-card" key={doc.id}><h3>{doc.school_name} · {statusLabel(doc.status)}</h3><SourceLink source={doc.source} /><p className="document-excerpt">{doc.excerpt}</p><button className="secondary" onClick={() => setSourceId(doc.source_id)}>查看擷取原文{doc.truncated ? '（部分）' : ''}</button></article>)}</>}{tab === 'audit' && audits.items.map(log => <details className="audit-row" key={log.id}><summary>{formatTime(log.created_at)} · {log.entity} #{log.entity_id} · {statusLabel(log.action)}</summary><h4>變更前</h4><pre>{JSON.stringify(log.before, null, 2)}</pre><h4>變更後</h4><pre>{JSON.stringify(log.after, null, 2)}</pre></details>)}{tab !== 'schools' && total === 0 && <p className="empty">此分類目前沒有資料。</p>}{tab !== 'schools' && total > 0 && <div className="pagination"><button disabled={page === 0} onClick={() => setPage(value => value - 1)}>上一頁</button><span>第 {page + 1} / {Math.ceil(total / 20)} 頁 · 共 {total} 筆</span><button disabled={(page + 1) * 20 >= total} onClick={() => setPage(value => value + 1)}>下一頁</button></div>}</>}</>}{sourceId !== null && <DocumentDialog sourceId={sourceId} token={token} refresh={reload} close={() => setSourceId(null)} />}</section>;
}
