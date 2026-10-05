'use client';
import { useState } from 'react';
import { type School } from '../lib/api';
import { formatTime, statusLabel } from '../lib/filters';
const example = JSON.stringify([{ id: 'school-id', name: '學校全名', short_name: '學校簡稱', city: '臺北市', district: '行政區', type: 'high_school', website: 'https://school.edu.tw', domains: ['school.edu.tw'], crawl_enabled: false }], null, 2);
export default function SchoolManager({ schools, busy, mutate }: { schools: School[]; busy: boolean; mutate: (path: string, body: unknown, message: string) => Promise<boolean> }) {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const rows = schools.filter(s => `${s.name} ${s.city}`.includes(query));
  async function importSchools() {
    setError('');
    try {
      const input: unknown = JSON.parse(text);
      if (!Array.isArray(input) || !input.length || input.length > 200 || input.some(row => !row || typeof row !== 'object' || !row.id || !row.name || !row.website || !Array.isArray(row.domains))) throw new Error('請輸入 1–200 所學校的 JSON 陣列，包含 id、name、website 與 domains。');
      if (await mutate('/api/admin/schools/import', { schools: input }, `已處理 ${input.length} 所學校。請確認官方網址，再啟用爬取。`)) setText('');
    } catch (error) { setError(error instanceof SyntaxError ? 'JSON 格式無效，請檢查引號、逗號與括號。' : (error as Error).message); }
  }
  return <><details className="import-panel"><summary>匯入或更新學校名冊</summary><p>輸入 JSON 陣列，每次最多 200 所。新學校預設暫停爬取，必須使用官方 edu.tw 網域。匯入相同 id 會更新既有資料。</p><pre>{example}</pre><label>學校 JSON<textarea value={text} onChange={event => setText(event.target.value)} rows={10} placeholder="貼上學校名冊陣列" /></label>{error && <p role="alert">{error}</p>}<button className="primary" disabled={!text.trim() || busy} onClick={importSchools}>驗證並匯入</button></details><label className="filter-label">搜尋學校<input value={query} onChange={event => { setQuery(event.target.value); setPage(0); }} placeholder="學校或縣市" /></label><div className="table-scroll"><table><thead><tr><th>學校</th><th>官方網址</th><th>爬取狀態</th><th>最近成功</th><th>操作</th></tr></thead><tbody>{rows.slice(page * 20, (page + 1) * 20).map(s => <tr key={s.id}><td>{s.name}<small>{s.city}{s.demo && ' · 示範學校'}</small></td><td><a className="text-link" href={s.website} target="_blank" rel="noopener noreferrer">開啟官網</a></td><td>{s.crawl_enabled ? statusLabel(s.crawler_status) : '暫停'}</td><td>{formatTime(s.last_success_at)}</td><td><button className="secondary" disabled={s.demo || busy} onClick={() => mutate(`/api/admin/schools/${s.id}/settings`, { crawl_enabled: !s.crawl_enabled }, s.crawl_enabled ? '已暫停學校爬取，未完成工作已取消。' : '已啟用學校爬取。')}>{s.crawl_enabled ? '暫停' : '啟用'}</button></td></tr>)}</tbody></table></div>{!rows.length ? <p className="empty">沒有符合條件的學校。</p> : <div className="pagination"><button disabled={page === 0} onClick={() => setPage(value => value - 1)}>上一頁</button><span>第 {page + 1} / {Math.ceil(rows.length / 20)} 頁 · 共 {rows.length} 所</span><button disabled={(page + 1) * 20 >= rows.length} onClick={() => setPage(value => value + 1)}>下一頁</button></div>}</>;
}
