'use client';
import { useState } from 'react';
import { request, type Subject } from '../lib/api';
import { gradeLabel } from '../lib/filters';
export default function ManualExamForm({ sourceId, token, done }: { sourceId: number; token: string; done: () => void }) {
  const now = new Date();
  const [year, setYear] = useState(String(now.getFullYear() - (now.getMonth() >= 7 ? 1911 : 1912)));
  const [semester, setSemester] = useState('1');
  const [number, setNumber] = useState('1');
  const [grade, setGrade] = useState('11');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [subjects, setSubjects] = useState<Subject[]>([{ name: '', scope: '', page_number: null }]);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function save() {
    setBusy(true); setError('');
    try {
      await request(`/api/admin/sources/${sourceId}/extract`, token, { method: 'POST', body: JSON.stringify({ academic_year: Number(year), semester: Number(semester), number: Number(number), grade: Number(grade), start_date: start || null, end_date: end || null, subjects, reason }) });
      done();
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  const change = (index: number, patch: Partial<Subject>) => setSubjects(current => current.map((subject, i) => i === index ? { ...subject, ...patch } : subject));
  return <form className="manual-form review-editor" onSubmit={event => { event.preventDefault(); save(); }}><h3>依原文建立待審核段考</h3><p>學校與來源固定為本文件。請核對公告的學年度、年級和段考次數；保存後仍需至待審核頁批准。</p><div className="filters"><label>學年度<input required type="number" min={100} max={999} value={year} onChange={event => setYear(event.target.value)} /></label><label>學期<select value={semester} onChange={event => setSemester(event.target.value)}><option value="1">第一學期</option><option value="2">第二學期</option></select></label><label>段考次數<select value={number} onChange={event => setNumber(event.target.value)}>{[1,2,3].map(n => <option key={n} value={n}>第 {n} 次</option>)}</select></label><label>年級<select value={grade} onChange={event => setGrade(event.target.value)}>{[10,11,12,7,8,9].map(g => <option key={g} value={g}>{gradeLabel(g)}</option>)}</select></label></div><div className="date-fields"><label>開始日期<input type="date" value={start} onChange={event => setStart(event.target.value)} /></label><label>結束日期<input type="date" value={end} onChange={event => setEnd(event.target.value)} /></label></div>{subjects.map((subject,index) => <div className="subject-editor" key={index}><label>科目<input required maxLength={50} value={subject.name} onChange={event => change(index,{name:event.target.value})} /></label><label>範圍<textarea required maxLength={2000} value={subject.scope} onChange={event => change(index,{scope:event.target.value})} /></label><label>來源頁數<input type="number" min={1} max={1000} value={subject.page_number || ''} onChange={event => change(index,{page_number:event.target.value ? Number(event.target.value) : null})} /></label><button type="button" disabled={subjects.length <= 1 || busy} onClick={() => setSubjects(current => current.filter((_, i) => i !== index))}>移除科目</button></div>)}<button className="secondary" type="button" disabled={subjects.length >= 40 || busy} onClick={() => setSubjects(current => [...current,{name:'',scope:'',page_number:null}])}>新增科目</button><label className="reason-field">整理備註（必填）<textarea required maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} placeholder="例如：自動解析失敗，依公告第 1 頁整理" /></label>{error && <p className="demo-notice" role="alert">{error}</p>}<button className="primary" disabled={busy || !reason.trim()}>{busy ? '儲存中…' : '建立待審核版本'}</button></form>;
}
