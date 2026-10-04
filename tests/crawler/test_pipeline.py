import asyncio
import sqlite3
import pytest
from crawler.pipeline import School,run_school,discover_links,extract_rules
from crawler.fetcher import validate_url,FetchError

SCHOOL=School('1','測試高中','https://school.edu.tw',['school.edu.tw'])
TEXT='測試高中\n115學年度 第一學期 第一次段考 高二\n數學A：1-1～2-2\n物理：Ch1～Ch2'

def test_external_links_are_not_queued():
    links=discover_links('<a href="/exam">第一次段考範圍</a><a href="https://evil.org/段考">段考</a>'.encode(),'https://school.edu.tw',['school.edu.tw'])
    assert len(links)==1 and links[0][0]>=180

def test_multi_grade_document_requires_layout_review():
    assert extract_rules([{'page':2,'text':TEXT+'\n高一'}],SCHOOL,SCHOOL.website)==[]

def test_source_provenance_and_conservative_confidence():
    result=extract_rules([{'page':2,'text':TEXT}],SCHOOL,SCHOOL.website)[0]
    assert result['grade']==11 and result['confidence']<.75
    assert result['subjects'][0]['page_number']==2
    assert result['subjects'][0]['evidence']=='數學A：1-1～2-2'

@pytest.mark.parametrize('url',['http://127.0.0.1/','http://school.edu.tw@127.0.0.1/','ftp://school.edu.tw/x','https://evil.school.edu.tw.evil.org/'])
def test_invalid_targets_rejected(url):
    with pytest.raises(FetchError): asyncio.run(validate_url(url,['school.edu.tw']))

def test_private_dns_rejected(monkeypatch):
    async def resolve(*args,**kwargs):return [(2,1,6,'',('10.0.0.1',443))]
    async def run():
        monkeypatch.setattr(asyncio.get_running_loop(),'getaddrinfo',resolve)
        with pytest.raises(FetchError):await validate_url(SCHOOL.website,SCHOOL.domains)
    asyncio.run(run())

class FakeFetcher:
    async def fetch(self,url,headers=None):
        return url,{'content-type':'text/html','etag':'test'},('<article>'+TEXT+'</article>').encode()

def test_unchanged_content_skips_extraction(tmp_path):
    path=str(tmp_path/'state.sqlite3')
    first=asyncio.run(run_school(SCHOOL,state_path=path,fetcher=FakeFetcher()))
    second=asyncio.run(run_school(SCHOOL,state_path=path,fetcher=FakeFetcher()))
    assert len(first.extractions)==1
    assert second.extractions==[] and second.documents==[]
    assert sqlite3.connect(path).execute('select status from frontier').fetchone()[0]=='fetched'

def test_failed_ingestion_remains_retryable(tmp_path):
    from crawler.pipeline import acknowledge_result
    path=str(tmp_path/'state.sqlite3')
    first=asyncio.run(run_school(SCHOOL,state_path=path,fetcher=FakeFetcher(),commit_state=False))
    retry=asyncio.run(run_school(SCHOOL,state_path=path,fetcher=FakeFetcher(),commit_state=False))
    assert len(first.extractions)==len(retry.extractions)==1
    acknowledge_result(path,SCHOOL.id,retry)
    after=asyncio.run(run_school(SCHOOL,state_path=path,fetcher=FakeFetcher(),commit_state=False))
    assert after.extractions==[]

def test_inherited_proxy_preserved(monkeypatch):
    from crawler.fetcher import Fetcher
    monkeypatch.setattr('crawler.fetcher.getproxies',lambda:{'https':'http://session-proxy:3128'})
    monkeypatch.setattr('crawler.fetcher.proxy_bypass',lambda host:False)
    fetcher=Fetcher(['school.edu.tw'])
    client=fetcher._client_for('https://school.edu.tw/')
    assert client._transport.proxied
    assert 'http://session-proxy:3128' in fetcher.clients
    asyncio.run(fetcher.close())

def test_crawler_info_url_configurable(monkeypatch):
    from crawler.fetcher import user_agent
    monkeypatch.setenv('CRAWLER_INFO_URL','https://radar.test/crawler')
    assert user_agent()=='ExamRadarBot/1.0 (+https://radar.test/crawler)'

def test_changed_known_document_checked_when_homepage_unchanged(tmp_path):
    class UpdatingFetcher:
        def __init__(self):self.round=1
        async def fetch(self,url,headers=None):
            if url==SCHOOL.website:
                if self.round==2:return url,{'content-type':'text/html'},b''
                return url,{'content-type':'text/html','etag':'home'},b'<a href="/exam.html">Exam range</a><a href="/exam.html">&#27573;&#32771;&#31684;&#22285;</a>'
            text=TEXT if self.round==1 else TEXT.replace('1-1～2-2','1-1～2-3')
            return url,{'content-type':'text/html','etag':str(self.round)},('<article>'+text+'</article>').encode()
    fetcher=UpdatingFetcher();path=str(tmp_path/'state.sqlite3')
    first=asyncio.run(run_school(SCHOOL,state_path=path,fetcher=fetcher))
    fetcher.round=2
    second=asyncio.run(run_school(SCHOOL,state_path=path,fetcher=fetcher))
    assert first.extractions[0]['subjects'][0]['scope']=='1-1～2-2'
    assert second.extractions[0]['subjects'][0]['scope']=='1-1～2-3'
    assert second.pages_checked==2

def test_percent_encoded_chinese_url_scored():
    from crawler.pipeline import score_url
    assert score_url('https://school.edu.tw/%E6%AE%B5%E8%80%83','')>=100
