import asyncio
import ipaddress
import socket
import time
import os
from urllib.request import getproxies, proxy_bypass
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import httpx

def user_agent():
    info=os.getenv('CRAWLER_INFO_URL','').strip()
    return 'ExamRadarBot/1.0'+(' (+'+info+')' if info else '')
class FetchError(ValueError): pass

async def validate_url(url, domains):
    p=urlparse(url); host=(p.hostname or '').lower().rstrip('.')
    if p.scheme not in ('http','https') or p.username or p.password or p.port not in (None,80,443):
        raise FetchError('Unsupported URL or credentials')
    if not any(host==d.lower() or host.endswith('.'+d.lower()) for d in domains):
        raise FetchError('Outside registered school domains')
    answers=await asyncio.get_running_loop().getaddrinfo(host,p.port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM)
    if not answers or any(not ipaddress.ip_address(a[4][0]).is_global for a in answers):
        raise FetchError('Private or non-public address blocked')
    return host

class PublicTransport(httpx.AsyncHTTPTransport):
    def __init__(self, *, proxy=None):
        self.proxied=bool(proxy)
        super().__init__(proxy=proxy)
    async def handle_async_request(self, request):
        # The inherited session proxy controls remote resolution and egress.
        # Destination DNS/domain checks occur before this transport; do not pin
        # a proxy request to an IP, which would bypass its hostname policy.
        if self.proxied:
            return await super().handle_async_request(request)
        host=request.url.host
        answers=await asyncio.get_running_loop().getaddrinfo(host,request.url.port,type=socket.SOCK_STREAM)
        ips=[ipaddress.ip_address(a[4][0]) for a in answers]
        if not ips or any(not ip.is_global for ip in ips): raise FetchError('Private address blocked at connection')
        headers=request.headers.copy(); headers['Host']=request.url.netloc.decode()
        extensions=dict(request.extensions); extensions['sni_hostname']=host
        pinned=httpx.Request(request.method,request.url.copy_with(host=str(ips[0])),headers=headers,stream=request.stream,extensions=extensions)
        return await super().handle_async_request(pinned)

class Fetcher:
    def __init__(self,domains,delay=1):
        self.domains=domains; self.delay=max(1,delay); self.last={}; self.robots={}
        self.clients={}
        self.agent=user_agent()
    def _client_for(self,url):
        parsed=urlparse(url)
        proxies=getproxies()
        proxy=None if proxy_bypass(parsed.hostname or '') else proxies.get(parsed.scheme) or proxies.get('all')
        if proxy not in self.clients:
            self.clients[proxy]=httpx.AsyncClient(transport=PublicTransport(proxy=proxy),timeout=20,headers={'User-Agent':self.agent},trust_env=False)
        return self.clients[proxy]
    async def close(self):
        for client in self.clients.values(): await client.aclose()
    async def _get(self,url,headers=None):
        host=await validate_url(url,self.domains)
        await asyncio.sleep(max(0,self.delay-(time.monotonic()-self.last.get(host,0))))
        self.last[host]=time.monotonic()
        for attempt in range(3):
            try:
                async with self._client_for(url).stream('GET',url,headers=headers) as r:
                    if r.status_code in (301,302,303,307,308): return r.status_code,r.headers,b''
                    if r.status_code==304: return 304,r.headers,b''
                    r.raise_for_status(); body=bytearray()
                    async for chunk in r.aiter_bytes():
                        body.extend(chunk)
                        if len(body)>12*1024*1024: raise FetchError('Document exceeds 12 MB')
                    return r.status_code,r.headers,bytes(body)
            except (httpx.TransportError,httpx.HTTPStatusError) as exc:
                if isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code<500 and exc.response.status_code!=429: raise
                if attempt==2: raise
                await asyncio.sleep(2**attempt)
    async def fetch(self,url,headers=None):
        for _ in range(6):
            await validate_url(url,self.domains)
            p=urlparse(url); origin=f'{p.scheme}://{p.netloc}'
            if origin not in self.robots:
                robot=RobotFileParser()
                try:
                    status,_,body=await self._get(origin+'/robots.txt')
                    if status!=200: raise FetchError('Cannot establish robots permission')
                    robot.parse(body.decode('utf-8',errors='replace').splitlines())
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code==404: robot.parse([])
                    else: raise FetchError('Cannot establish robots permission') from exc
                self.robots[origin]=robot
            robot=self.robots[origin]
            if not robot.can_fetch(self.agent,url): raise FetchError('Blocked by robots.txt')
            self.delay=max(self.delay,robot.crawl_delay(self.agent) or robot.crawl_delay('*') or 0)
            status,h,body=await self._get(url,headers)
            if status in (301,302,303,307,308):
                if not h.get('location'): raise FetchError('Missing redirect location')
                url=urljoin(url,h['location']); headers=None; continue
            return url,h,body
        raise FetchError('Too many redirects')
