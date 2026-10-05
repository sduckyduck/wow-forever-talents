"""Fetch public Forever quest metadata, splitting capped list responses.

Only metadata/facts are republished. Original HTML stays in the local raw cache.
"""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.request

HERE = Path(__file__).resolve().parent
RAW = HERE / 'raw'
RAW.mkdir(parents=True, exist_ok=True)


def fetch(lo, hi, side=None, reqlo=None, reqhi=None):
    url = f'https://www.wowhead.com/forever/quests/min-level:{lo}/max-level:{hi}'
    if side is not None:
        url += f'/side:{side}'
    if reqlo is not None:
        url += f'/min-req-level:{reqlo}/max-req-level:{reqhi}'
    path = RAW / f'wowhead-level-{lo}-{hi}{"-side-"+str(side) if side else ""}{f"-req-{reqlo}-{reqhi}" if reqlo is not None else ""}.html'
    if not path.exists():
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=40) as response:
                    data = response.read()
                path.write_bytes(data)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 + attempt)
    data = path.read_bytes()
    page = data.decode('utf8')
    match = re.search(r"new Listview\(\{template: 'quest'.*?\bdata:\s*", page)
    if not match and 'Your criteria did not match any quests.' in page:
        rows = []
    elif not match:
        raise ValueError(f'No quest list: {url}')
    else:
        rows, _ = json.JSONDecoder().raw_decode(page[match.end():])
    if not isinstance(rows, list) or any(not lo <= q['level'] <= hi for q in rows) or (side is not None and any(q['side'] not in {side, 3} for q in rows)):
        raise ValueError(f'Level filter did not apply: {url}')
    if reqlo is not None and any(not reqlo <= q['reqlevel'] <= reqhi for q in rows):
        raise ValueError(f'Required level filter did not apply: {url}')
    proof = {'url': url, 'file': path.name, 'sha256': hashlib.sha256(data).hexdigest(),
             'count': len(rows), 'readAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    return rows, proof


def main():
    pending = [(-1, 0, None, None, None), (1, 9, None, None, None), (10, 19, None, None, None), (20, 29, None, None, None), (30, 39, None, None, None), (40, 49, None, None, None), (50, 59, None, None, None), (60, 60, None, None, None), (61, 255, None, None, None)]
    result, proofs = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        while pending:
            batch, pending = pending, []
            futures = {pool.submit(fetch, *args): args for args in batch}
            for future in concurrent.futures.as_completed(futures):
                a, b, side, reqlo, reqhi = futures[future]
                rows, proof = future.result()
                proofs.append(proof)
                print(f'{a}-{b}: {len(rows)}', flush=True)
                if len(rows) >= 1000:
                    if a == b and reqlo is None:
                        pending.extend([(a, b, side, r, min(r+9, 255)) for r in range(0, 256, 10)])
                        continue
                    if a == b and reqlo < reqhi:
                        mid = (reqlo+reqhi)//2
                        pending.extend([(a,b,side,reqlo,mid),(a,b,side,mid+1,reqhi)])
                        continue
                    if a == b:
                        raise ValueError(f'Single level {a} hit cap; add a category partition')
                    mid = (a+b)//2
                    pending.extend([(a, mid, side, reqlo, reqhi), (mid+1, b, side, reqlo, reqhi)])
                else:
                    result.update({q['id']: q for q in rows})
    output = {'source': 'Wowhead Forever public quest metadata', 'rows': list(result.values()), 'responses': proofs}
    (RAW / 'wowhead-catalog.json').write_text(json.dumps(output, ensure_ascii=False), encoding='utf8')
    print(f'Unique quests: {len(result)}')


if __name__ == '__main__':
    main()
