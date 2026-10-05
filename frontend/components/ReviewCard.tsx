'use client';
import { useState } from 'react';
import { request, type Review, type Subject, type Version } from '../lib/api';
import { gradeLabel } from '../lib/filters';
import { SourceLink } from './ExamDialog';
export default function ReviewCard({ review, token, refresh, document }: { review: Review; token: string; refresh: () => void; document: (id: number) => void }) {
  const [version, setVersion] = useState(review.version);
  const [editing, setEditing] = useState(false);
  const [start, setStart] = useState(version.start_date || '');
  const [end, setEnd] = useState(version.end_date || '');
  const [subjects, setSubjects] = useState<Subject[]>(version.subjects.map(s => ({ ...s })));
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  async function act(action: 'edit' | 'approve' | 'reject') {
    setBusy(true); setError(''); setSaved(false);
    try {
      const body = action === 'edit' ? { expected_revision: version.revision, start_date: start || null, end_date: end || null, subjects: subjects.map(s => ({ name: s.name, scope: s.scope, page_number: s.page_number || null })), reason } : { expected_revision: version.revision, reason };
      const result = await request<Version>(`/api/admin/review/${review.id}/${action}`, token, { method: 'POST', body: JSON.stringify(body) });
      if (action === 'edit') { setVersion(result); setEditing(false); setReason(''); setSaved(true); } else refresh();
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  const changeSubject = (index: number, patch: Partial<Subject>) => setSubjects(current => current.map((subject, i) => i === index ? { ...subject, ...patch } : subject));
  return <article className="review-card"><h3>{review.exam.school_name}</h3><p>{review.exam.academic_year}-{review.exam.semester} · 第 {review.exam.number} 次段考 · {gradeLabel(review.exam.grade)} · 版本 {version.version}</p><p className="muted">抽取信心值 {Math.round(version.confidence * 100)}% · 請核對日期、年級與所有科目。</p><SourceLink source={version.source} /><button className="text-link" onClick={() => document(version.source.id)}>查看文件擷取原文</button>{error && <p className="demo-notice" role="alert">{error}</p>}{saved && <p role="status">修正已保存，可核對後批准。</p>}{editing ? <div className="review-editor"><div className="date-fields"><label>開始日期<input type="date" value={start} onChange={event => setStart(event.target.value)} /></label><label>結束日期<input type="date" value={end} onChange={event => setEnd(event.target.value)} /></label></div>{subjects.map((subject, index) => <div className="subject-editor" key={index}><label>科目<input required maxLength={50} value={subject.name} onChange={event => changeSubject(index, { name: event.target.value })} /></label><label>範圍<textarea required maxLength={2000} value={subject.scope} onChange={event => changeSubject(index, { scope: event.target.value })} /></label><label>來源頁數<input type="number" min={1} max={1000} value={subject.page_number || ''} onChange={event => changeSubject(index, { page_number: event.target.value ? Number(event.target.value) : null })} /></label><button disabled={subjects.length <= 1 || busy} onClick={() => setSubjects(current => current.filter((_, i) => i !== index))}>移除科目</button></div>)}<button className="secondary" disabled={subjects.length >= 40 || busy} onClick={() => setSubjects(current => [...current, { name: '', scope: '', page_number: null }])}>新增科目</button></div> : <><p>{version.start_date || '日期待確認'}{version.end_date && ` — ${version.end_date}`}</p><div className="subject-list">{version.subjects.map(subject => <div key={subject.name}><span>{subject.name}</span><strong>{subject.scope}{subject.page_number && <small> · 第 {subject.page_number} 頁</small>}</strong></div>)}</div></>}<label className="reason-field">{editing ? '修正原因（必填）' : '審核備註'}<textarea maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} placeholder={editing ? '例如：依公告第 2 頁修正數學範圍' : '例如：已核對校方原公告'} /></label><div className="actions">{editing ? <><button className="primary" disabled={busy || !reason.trim() || subjects.some(s => !s.name.trim() || !s.scope.trim())} onClick={() => act('edit')}>保存修正</button><button className="secondary" disabled={busy} onClick={() => { setEditing(false); setStart(version.start_date || ''); setEnd(version.end_date || ''); setSubjects(version.subjects.map(s => ({ ...s }))); setReason(''); }}>取消編輯</button></> : <><button className="primary" disabled={busy} onClick={() => act('approve')}>批准發布</button><button className="secondary" disabled={busy} onClick={() => setEditing(true)}>編輯範圍</button><button className="secondary" disabled={busy} onClick={() => act('reject')}>拒絕</button></>}</div></article>;
}
