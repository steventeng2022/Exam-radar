"""Bounded priority crawl; uncertain rule extractions always require review."""
import hashlib
import heapq
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urljoin,urlparse,urldefrag,unquote
from bs4 import BeautifulSoup
from .fetcher import Fetcher
from .parsers import parse_document

@dataclass
class School:
    id: str
    name: str
    website: str
    domains: list[str]

@dataclass
class CrawlResult:
    documents: list=field(default_factory=list)
    extractions: list=field(default_factory=list)
    errors: list=field(default_factory=list)
    pages_checked: int=0
    state_updates: list=field(default_factory=list)

WEIGHTS={'段考':100,'定期考':100,'範圍':80,'考程':70,'試務':40,'教務':30,'教學':20,'公告':10,'最新消息':10}
def score_url(url,text):
    value=unquote(url)+' '+text
    return sum(weight for keyword,weight in WEIGHTS.items() if keyword in value)+(50 if str(date.today().year-1911) in value else 0)

def discover_links(body,url,domains):
    soup=BeautifulSoup(body,'html.parser'); links=[]
    for a in soup.find_all('a',href=True):
        target=urldefrag(urljoin(url,a['href']))[0]; p=urlparse(target)
        host=(p.hostname or '').lower()
        if p.scheme in ('http','https') and any(host==d or host.endswith('.'+d) for d in domains):
            text=a.get_text(' ',strip=True)
            links.append((score_url(target,text),target,text))
    return links

SUBJECTS='數學A|數學B|國文|英文|數學|物理|化學|生物|地理|歷史|公民|地科'
def extract_rules(pages,school,url):
    text='\n'.join(p['text'] for p in pages)
    if not re.search('段考|定期考|期中考',text): return []
    # Domain proves publication origin, not which school's exam an announcement describes.
    if school.name not in text: return []
    year=re.search(r'(\d{3})\s*學年度',text)
    sem=re.search(r'第?\s*([一二12])\s*學期',text)
    exam=re.search(r'第\s*([一二三123])\s*次\s*(?:段考|定期考)',text)
    # A multi-grade table needs a layout-aware extractor; never assign all rows to one grade.
    grades=set(re.findall(r'高([一二三123])',text))
    if not year or not sem or not exam or len(grades)!=1: return []
    nums={'一':1,'二':2,'三':3,'1':1,'2':2,'3':3}
    subjects=[]
    for page in pages:
        for m in re.finditer(r'('+SUBJECTS+r')\s*[:：|]?\s*([^\n]{2,100})',page['text']):
            scope=m.group(2).strip()
            if re.search(r'\d|[一二三四五六七八九十]|Ch|L',scope):
                subjects.append({'name':m.group(1),'scope':scope,'evidence':m.group(0),'page_number':page['page']})
    if not subjects: return []
    academic_year=int(year[1])
    if not 100<=academic_year<=date.today().year-1911+1: return []
    return [{'source_url':url,'academic_year':academic_year,'semester':nums[sem[1]],'number':nums[exam[1]],'grade':9+nums[next(iter(grades))],'start_date':None,'end_date':None,'confidence':0.65,'subjects':subjects,'review_required':True,'extraction_method':'rules'}]

class State:
    """SQLite frontier survives interruption; each run revalidates known URLs.

    A 304 homepage must not prevent checking an updated PDF already discovered.
    """
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS frontier (school TEXT,url TEXT,priority INTEGER,status TEXT,hash TEXT,etag TEXT,modified TEXT,PRIMARY KEY(school,url))')
        self.db.commit()
    def enqueue(self,school,url,priority):
        if self.db.execute('SELECT count(*) FROM frontier WHERE school=?',(school,)).fetchone()[0]>=10000:
            return
        self.db.execute('INSERT OR IGNORE INTO frontier(school,url,priority,status) VALUES(?,?,?,?)',(school,url,priority,'queued')); self.db.commit()
    def known_urls(self,school):
        return self.db.execute("SELECT url,priority + CASE WHEN hash IS NULL THEN 500 ELSE 0 END AS effective FROM frontier WHERE school=? ORDER BY effective DESC LIMIT 10000",(school,)).fetchall()
    def previous(self,school,url):
        return self.db.execute('SELECT hash,etag,modified FROM frontier WHERE school=? AND url=?',(school,url)).fetchone()
    def done(self,school,url,digest,headers):
        self.db.execute('UPDATE frontier SET status=?,hash=?,etag=?,modified=? WHERE school=? AND url=?',('fetched',digest,headers.get('etag'),headers.get('last-modified'),school,url)); self.db.commit()

async def run_school(school,*,max_pages=40,state_path=None,fetcher=None,commit_state=True,on_progress=None):
    """Returns CrawlResult with documents, extractions, errors; never publishes directly."""
    if isinstance(school,dict): school=School(**school)
    max_pages=min(max(int(max_pages),1),100)
    state=State(state_path) if state_path else None
    owned=fetcher is None; fetcher=fetcher or Fetcher(school.domains)
    queue=[(-1000,school.website,'首頁')]; seen=set(); result=CrawlResult()
    if state:
        state.enqueue(str(school.id),school.website,1000)
        queue.extend((-priority,url,'') for url,priority in state.known_urls(str(school.id)))
        heapq.heapify(queue)
    try:
        while queue and result.pages_checked<max_pages:
            _,url,title=heapq.heappop(queue)
            if url in seen: continue
            if on_progress: await on_progress(result.pages_checked)
            seen.add(url); result.pages_checked+=1
            try:
                previous=state.previous(str(school.id),url) if state else None
                headers={}
                if previous and previous[1]: headers['If-None-Match']=previous[1]
                if previous and previous[2]: headers['If-Modified-Since']=previous[2]
                final,h,body=await fetcher.fetch(url,headers)
                if not body:
                    if state and previous:
                        result.state_updates.append({'url':url,'hash':previous[0],'headers':{'etag':previous[1],'last-modified':previous[2]}})
                    continue
                digest=hashlib.sha256(body).hexdigest(); mime=h.get('content-type','text/html').split(';')[0]
                if 'html' in mime:
                    for priority,target,label in sorted(discover_links(body,final,school.domains),reverse=True)[:200]:
                        if priority>0 and target not in seen:
                            heapq.heappush(queue,(-priority,target,label))
                            if state: state.enqueue(str(school.id),target,priority)
                if previous and digest==previous[0]:
                    if state:
                        result.state_updates.append({'url':url,'hash':digest,'headers':dict(h)})
                        if commit_state: state.done(str(school.id),url,digest,h)
                    continue
                pages=parse_document(body,final,mime)
                text='\n'.join(p['text'] for p in pages)
                if re.search('段考|定期考|期中考',text):
                    result.documents.append({'url':final,'title':title or final,'content_hash':digest,'source_type':'html' if 'html' in mime else 'document','text':text[:100000],'pages':pages})
                    result.extractions.extend(extract_rules(pages,school,final))
                if state:
                    result.state_updates.append({'url':url,'hash':digest,'headers':dict(h)})
                    if commit_state: state.done(str(school.id),url,digest,h)
            except Exception as exc:
                result.errors.append({'url':url,'message':str(exc)[:500]})
    finally:
        if owned: await fetcher.close()
        if state: state.db.close()
    return result


def acknowledge_result(state_path,school_id,result):
    """Call only after the document/exam database transaction commits."""
    state=State(state_path)
    try:
        for update in result.state_updates:
            state.done(str(school_id),update['url'],update['hash'],update['headers'])
    finally:
        state.db.close()
