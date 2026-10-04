import argparse,asyncio,json
from dataclasses import asdict
from urllib.parse import urlparse
from .pipeline import School,run_school

def main():
    p=argparse.ArgumentParser(description='Bounded public-school crawler; uncertain output requires review')
    p.add_argument('url');p.add_argument('--name',required=True);p.add_argument('--id',default='manual');p.add_argument('--max-pages',type=int,default=40);p.add_argument('--state',default='crawler-state.sqlite3')
    args=p.parse_args()
    school=School(args.id,args.name,args.url,[urlparse(args.url).hostname])
    result=asyncio.run(run_school(school,max_pages=min(max(args.max_pages,1),100),state_path=args.state))
    print(json.dumps(asdict(result),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
