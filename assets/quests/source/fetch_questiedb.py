"""Pin Questie's maintained Forever source data without running upstream code."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

BASE=Path(__file__).resolve().parent/'raw/questiedb'
BASE.mkdir(parents=True,exist_ok=True)
previous=BASE/'snapshot.json'
revision=json.loads(previous.read_text())['commit'] if previous.exists() else 'master'
tree=json.load(urllib.request.urlopen(f'https://api.github.com/repos/Questie/QuestieDB/git/trees/{revision}?recursive=1',timeout=40))
sha=tree['sha']
paths=[x['path'] for x in tree['tree'] if (
    x['path'].startswith('data/Forever/') and x['path'].endswith(('.lua','.json')) or
    x['path'].startswith('l10n/Forever/') and x['path'].endswith('/zhCN.lua') or
    x['path'] in ['docs/forever-data.md','docs/forever.md','PROVENANCE.md','docs/forever-coordinate-audit.md','docs/forever-delta-base.md','src/meta/questMeta.lua','enum/quest.lua','enum/quests.lua','enum/npcs.lua','enum/objects.lua','enum/items.lua','LICENSE'] or
    x['path'].startswith('src/corrections/enum/') and x['path'].endswith('.lua') or
    x['path'] in ['docs/adr/0016-table-correction-operations.md','docs/api.md'] or
    x['path'].startswith('src/corrections/Forever/') and x['path'].endswith('.lua') or
    x['path'] in ['support/Forever/Zones/areaIdToUiMapId.lua','support/Forever/Zones/dungeons.lua','support/Forever/Zones/instanceIdToAreaId.lua','support/Forever/Zones/subZoneToParentZone.lua'])]
def fetch(path):
    url=f'https://raw.githubusercontent.com/Questie/QuestieDB/{sha}/{path}'
    target=BASE/path
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():data=target.read_bytes()
    else:
        with urllib.request.urlopen(url,timeout=50) as r:data=r.read()
        target.write_bytes(data)
    return {'file':path,'url':url,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:manifest=list(pool.map(fetch,paths))
(BASE/'snapshot.json').write_text(json.dumps({'commit':sha,'files':manifest},indent=2),encoding='utf8')
print(json.dumps({'commit':sha,'files':len(paths),'bytes':sum(x['bytes'] for x in manifest)},indent=2))
