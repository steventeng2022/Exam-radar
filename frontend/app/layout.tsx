import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {title:'Exam Radar｜全台段考情報',description:'搜尋公開段考範圍，比較學校進度，回溯每一份原始公告。'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="zh-Hant"><body>{children}</body></html>}
