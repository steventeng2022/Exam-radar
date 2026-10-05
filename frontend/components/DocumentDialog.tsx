'use client';
import { useEffect, useState } from 'react';
import { request, type ParsedDocument } from '../lib/api';
import Dialog from './Dialog';
import { SourceLink } from './ExamDialog';
import ManualExamForm from './ManualExamForm';
export default function DocumentDialog({ sourceId, token, close, refresh }: { sourceId: number; token: string; close: () => void; refresh: () => void }) {
  const [data, setData] = useState<ParsedDocument | null>(null);
  const [error, setError] = useState('');
  const [created, setCreated] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    request<ParsedDocument>(`/api/admin/sources/${sourceId}/document`, token, { signal: controller.signal }).then(setData).catch(error => { if (!controller.signal.aborted) setError(error.message); });
    return () => controller.abort();
  }, [sourceId, token]);
  return <Dialog title="擷取原文" close={close}><h2>文件擷取原文</h2>{error ? <p role="alert">{error}</p> : !data ? <p role="status">讀取文件…</p> : <><SourceLink source={data.source} />{data.truncated && <p className="demo-notice">文件過長，以下只保留部分文字；請開啟原公告核對完整內容。</p>}{data.pages.length ? data.pages.map((page, index) => <details className="document-page" key={index} open={index === 0}><summary>{page.sheet || (page.page ? `第 ${page.page} 頁` : '公告文字')}</summary><pre>{page.text}</pre></details>) : <pre className="document-text">{data.text}</pre>}{created ? <p className="success-notice" role="status">待審核版本已建立。關閉文件後，到待審核頁核對並批准。</p> : <details className="manual-entry"><summary>建立待審核段考</summary><ManualExamForm sourceId={sourceId} token={token} done={() => { setCreated(true); refresh(); }} /></details>}</>}</Dialog>;
}
