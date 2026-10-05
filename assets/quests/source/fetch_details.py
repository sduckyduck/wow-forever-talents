"""Capture current quest facts; never republish story prose or comments.

Three concurrent requests, resumable local snapshots, finite retries. Extract
only structured metadata, NPC/object locations and referenced item facts.
"""
import concurrent.futures
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.request
import argparse
import threading
from urllib.error import HTTPError

HERE=Path(__file__).resolve().parent
RAW=HERE/'raw/details'
RAW.mkdir(parents=True,exist_ok=True)
DECODER=json.JSONDecoder()
BLOCKED=threading.Event()


def decode_after(page,pattern):
    match=re.search(pattern,page)
    if not match:return None
    try:return DECODER.raw_decode(page[match.end():])[0]
    except ValueError:return None


def fetch(q):
    qid=q['id']
    path=RAW/f'{qid}.html.gz'
    url=f'https://www.wowhead.com/forever/cn/quest={qid}'
    for attempt in range(3):
        try:
            if BLOCKED.is_set() and not path.exists():return qid,{'error':'Stopped after HTTP 403; no retry or bypass','url':url}
            if path.exists():data=gzip.decompress(path.read_bytes())
            else:
                with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as r:data=r.read()
                path.write_bytes(gzip.compress(data,mtime=0))
            page=data.decode('utf8')
            meta=decode_after(page,rf'g_quests\[{qid}\]\s*,\s*')
            if not meta or meta.get('id')!=qid:raise ValueError('No matching quest metadata')
            mapper=decode_after(page,r'new Mapper\(')
            entities={}
            for match in re.finditer(r'WH\.Gatherer\.addData\(([123]),\s*16,\s*',page):
                group,_=DECODER.raw_decode(page[match.end():])
                kind={'1':'npc','2':'object','3':'item'}[match.group(1)]
                for rid,row in group.items():
                    entities[f'{kind}:{rid}']={k:v for k,v in row.items() if k in ['name_enus','name_zhcn','icon','quality','jsonequip']}
            positions=[]
            for zone,info in (mapper or {}).get('objectives',{}).items():
                for floor,points in enumerate(info.get('levels',[])):
                    for p in points:
                        if p.get('type') not in [1,2] or not p.get('id'):continue
                        kind='npc' if p['type']==1 else 'object'
                        positions.append({'entity':f'{kind}:{p["id"]}','name':p.get('name',''),
                                          'zone':int(zone),'floor':floor,'role':p.get('point','objective'),
                                          'coords':p.get('coords') or ([p['coord']] if p.get('coord') else [])})
            # Referenced items include objectives and rewards. Their relation is
            # kept explicit; an item mentioned in prose is never a drop source.
            return qid,{'meta':meta,'positions':positions,'entities':entities,
                         'source':{'url':url,'sha256':hashlib.sha256(data).hexdigest(),
                                   'readAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}}
        except Exception as e:
            if isinstance(e,HTTPError) and e.code in [403,429]:
                BLOCKED.set();return qid,{'error':str(e),'url':url}
            if attempt==2:return qid,{'error':str(e),'url':url}
            time.sleep(1+attempt)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=0)
    args=parser.parse_args()
    catalog=json.loads((HERE/'raw/wowhead-catalog.json').read_text(encoding='utf8'))['rows']
    catalog.sort(key=lambda q:(0 if q.get('envChange',{}).get('status')=='new' else 1 if q.get('envChange',{}).get('status')=='updated' else 2,q['level'],q['id']))
    if args.limit:catalog=catalog[:args.limit]
    destination=HERE/'raw/wowhead-details.json'
    result=json.loads(destination.read_text(encoding='utf8')) if destination.exists() else {}
    pending=[q for q in catalog if str(q['id']) not in result or 'error' in result[str(q['id'])]]
    def save():destination.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for i,(qid,row) in enumerate(pool.map(fetch,pending),1):
            result[str(qid)]=row
            if '403' in row.get('error','') or '429' in row.get('error',''):
                save();print('Source denied further requests; saved available snapshots and stopped.',flush=True);break
            if i%25==0 or i==len(pending):
                save();print(f'{i}/{len(pending)} fetched; total {len(result)}, failures {sum("error" in x for x in result.values())}',flush=True)
    save()


if __name__=='__main__':main()
