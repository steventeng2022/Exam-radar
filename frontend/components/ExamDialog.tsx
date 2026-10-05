'use client';
import { useEffect, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { request, type Exam, type Source } from '../lib/api';
import { gradeLabel, formatTime } from '../lib/filters';
import Dialog from './Dialog';
export function SourceLink({ source }: { source: Source }) {
  if (source.demo) return <div className="source-link">{source.title} · 示範資料，無正式公告</div>;
  return <a className="source-link" href={source.url} target="_blank" rel="noopener noreferrer">{source.title || '查看原始公告'}<ExternalLink size={16} /></a>;
}
export default function ExamDialog({ exam, close }: { exam: Exam; close: () => void }) {
  const [detail, setDetail] = useState(exam);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    request<Exam>('/api/exams/' + exam.id, undefined, { signal: controller.signal }).then(setDetail).catch(error => { if (!controller.signal.aborted) setError(error.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [exam.id]);
  return <Dialog title="段考詳情" close={close}><div className="eyebrow">EXAM INTELLIGENCE</div><h2>{detail.school_name}</h2><p>{detail.academic_year} 學年度第 {detail.semester} 學期 · 第 {detail.number} 次段考 · {gradeLabel(detail.grade)}</p>{detail.demo && <div className="demo-notice">示範資料，請勿作為正式備考依據。</div>}<div className="exam-date">{detail.start_date || '日期待確認'}{detail.end_date && ' — ' + detail.end_date}</div><div className="subject-list detail-subjects">{detail.subjects.map(subject => <div key={subject.name}><span>{subject.name}</span><strong>{subject.scope}{subject.page_number && <small> · 第 {subject.page_number} 頁</small>}</strong></div>)}</div><h3>原始來源</h3>{detail.sources.map(source => <SourceLink key={source.id} source={source} />)}<p className="muted">資料整理：{formatTime(detail.updated_at)}</p><h3>版本紀錄</h3>{loading && <p role="status">讀取完整紀錄…</p>}{error && <p className="error-message" role="alert">{error} 目前顯示列表中的版本。</p>}{detail.versions.map(version => <details className="version-details" key={version.id}><summary>版本 {version.version} · {formatTime(version.created_at)}</summary><p>{version.start_date || '日期待確認'}{version.end_date && ' — ' + version.end_date}</p>{version.subjects.map(subject => <div key={subject.name}>{subject.name}：{subject.scope}</div>)}<SourceLink source={version.source} /></details>)}<p className="detail-warning">範圍由系統整理，正式備考請核對學校最新原公告。</p></Dialog>;
}
