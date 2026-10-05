"""Build an auditable quest catalogue shared by the site and future addon.

Client IDs are an inventory, never proof of availability. Classic relationships
remain explicitly labelled; current Forever metadata and observed fields overlay
them independently. No account or character data is emitted.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import csv
from datetime import datetime, timezone
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'talent/site/assets/quests'
CLIENT = Path('D:/World of Warcraft/_classic_beta_')
QUESTIE = CLIENT / 'Interface/AddOns/Questie'
UPSTREAM = HERE / 'raw/questiedb'
BUILD = '1.60.1.70205'
DB = ROOT / f'output/wow-cinema/index/{BUILD}-quests-zhCN/db2'
ENTITY_DB = ROOT / f'output/wow-cinema/index/{BUILD}-quest-entities-zhCN/db2'
sys.path.insert(0, str(ROOT / '.cache/quest-deps'))
from lupa.lua51 import LuaRuntime, lua_type

lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
modules = {}
QuestieLoader = {}
function QuestieLoader:ImportModule(name)
    if not modules[name] then modules[name] = {} end
    return modules[name]
end
QuestieLoader.CreateModule = QuestieLoader.ImportModule
function GetLocale() return 'zhCN' end
Questie = {IsForever=true,IsClassic=true}
modules.l10n = setmetatable({questLookup={},npcLookup={},objectLookup={},itemLookup={}}, {__call=function(t,x) return x end})
modules.QuestieCorrections = {itemObjectiveFirst={},itemObjectiveLast={},killCreditObjectiveFirst={}}
modules.Expansions = {Current=1,Era=1,Tbc=2,Wrath=3,Wotlk=3,Cata=4,Mop=5}
Expansions=modules.Expansions
os=nil;io=nil;package=nil;require=nil;dofile=nil;loadfile=nil
''')
modules = lua.globals().modules
sources, corrections = [], []


def source(path, kind):
    data = path.read_bytes()
    # SavedVariables paths contain account IDs. Record a generic source name.
    name = str(path.relative_to(ROOT)).replace('\\','/') if path.is_relative_to(ROOT) else str(path.relative_to(CLIENT)).replace('\\','/') if path.is_relative_to(CLIENT) else path.name
    if '/Account/' in name:
        name = 'WTF/Account/<local-account>/SavedVariables/Questie.lua'
    sources.append({'file':name,'kind':kind,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    return data.decode('utf-8-sig', errors='replace' if kind=='local-game-observation' else 'strict')


def table_end(s, start):
    """Balanced literal scanner that respects comments and quoted braces."""
    depth, i = 0, start
    while i < len(s):
        if s.startswith('--', i):
            j=s.find('\n',i); i=len(s) if j<0 else j+1; continue
        if s[i] in "\"'":
            quote=s[i]; i+=1
            while i<len(s):
                if s[i]=='\\': i+=2; continue
                if s[i]==quote: i+=1; break
                i+=1
            continue
        if s[i]=='{': depth+=1
        if s[i]=='}':
            depth-=1
            if depth==0: return i+1
        i+=1
    raise ValueError('Unclosed Lua table')


def constants(path, owner):
    s = source(path, 'questie-classic-schema')
    if modules[owner] is None: modules[owner]=lua.table()
    lua.globals()[owner]=modules[owner]
    for m in re.finditer(re.escape(owner)+r'\.([A-Za-z]+)\s*=\s*\{',s):
        start=m.end()-1
        # Only literal constants above runtime initialization are needed.
        try:
            modules[owner][m.group(1)] = lua.execute('return '+s[start:table_end(s,start)])
        except Exception as error:
            if m.group(1) in ['npcFlags','raceKeys','classKeys','sortKeys','specializationKeys','professionKeys','waypointPresets']:
                raise ValueError(f'Constant {owner}.{m.group(1)}: {error}') from error


def arr(t):
    if lua_type(t) != 'table': return []
    return [v for k,v in sorted(t.items(),key=lambda x: x[0] if isinstance(x[0],(int,float)) else 1e12) if isinstance(k,(int,float))]


def plain(t):
    if lua_type(t) != 'table': return t
    return {str(k):plain(v) for k,v in t.items()}


def db(table, folder=DB):
    path=folder/f'{table}.json'
    source(path, 'local-client-db2')
    return json.loads(path.read_text(encoding='utf8'))


def load_data(kind):
    path=UPSTREAM/f'data/Forever/forever{kind.title()}DB.lua'
    s=source(path,'questiedb-forever-coordinate-seed')
    head=s[:s.index('[[return')]
    lua.execute(head+'nil')
    code=re.search(r'\[\[(return \{.*?)\]\]',s,re.S).group(1)
    return lua.execute(code)


lua.execute(source(QUESTIE/'Database/Zones/data/zoneIds.lua','questie-classic-schema'))
lua.globals().ZoneDB=modules.ZoneDB
constants(QUESTIE/'Database/QuestieDB.lua','QuestieDB')
constants(QUESTIE/'Database/Constants.lua','QuestieDB')
constants(QUESTIE/'Database/questDB.lua','QuestieDB')
constants(QUESTIE/'Database/npcDB.lua','QuestieDB')
constants(QUESTIE/'Database/objectDB.lua','QuestieDB')
constants(QUESTIE/'Database/itemDB.lua','QuestieDB')
constants(QUESTIE/'Modules/QuestieProfessions.lua','QuestieProfessions')
lua.execute(source(QUESTIE/'Database/Zones/data/zoneIds.lua','questie-classic-schema'))
data={kind:load_data(kind) for kind in ['quest','npc','object','item']}
seed_names={kind:{rid:row[1] for rid,row in rows.items()} for kind,rows in data.items()}
s=source(QUESTIE/'Modules/Phasing.lua','questie-classic-schema')
m=re.search(r'local phases\s*=\s*\{',s); start=m.end()-1
modules.Phasing=lua.table(); modules.Phasing.phases=lua.execute('return '+s[start:table_end(s,start)])
namespace=lua.table(Enum=lua.table())
for path in sorted((UPSTREAM/'src/corrections/enum').glob('*.lua')):
    if path.name=='constants.lua':continue
    lua.execute(source(path,'questiedb-forever-schema'),'QuestieDB',namespace)
enums=namespace.Enum
for key in ['raceKeys','classKeys','npcFlags']:
    value=enums.byExpansion.Forever[key] or enums.byExpansion.Classic[key]
    if value is not None:modules.QuestieDB[key]=value
for key in ['specialFlags','questFlags','sortKeys','factionIDs','waypointPresets','itemClasses']:
    if enums[key] is not None:modules.QuestieDB[key]=enums[key]
modules.ZoneDB.zoneIDs=enums.zoneIDs
for key in ['professionKeys','specializationKeys','rankNames']:
    if enums[key] is not None:modules.QuestieProfessions[key]=enums[key]
if enums.phases is not None:modules.Phasing.phases=enums.phases
for kind in data:
    keys=modules.QuestieDB[kind+'Keys']
    for key,index in list(keys.items()):
        if isinstance(index,(int,float)):
            keys[key+'_add']=index+1000;keys[key+'_remove']=index-1000

# Canonical field operations preserve group meaning and exact complete records.
# Provenance is retained per field; an inherited field is never relabelled by an
# unrelated Forever correction to the same quest or entity.
field_sources={kind:defaultdict(dict) for kind in data}
def unlua(value):
    if lua_type(value)!='table':return value
    return {k:unlua(v) for k,v in value.items()}
def to_lua(value):
    if isinstance(value,dict):return lua.table_from({k:to_lua(v) for k,v in value.items()})
    return value
def listop(old,operand,add):
    values=[v for _,v in sorted((old or {}).items())]
    for _,v in sorted(operand.items()):
        if add and v not in values:values.append(deepcopy(v))
        if not add:values=[x for x in values if x!=v]
    return {i+1:v for i,v in enumerate(values)}
def operate(kind,index,old,operand,add):
    grouped=(kind=='quest' and index in [2,3,10]) or (kind=='npc' and index in [7,8]) or (kind=='object' and index==4)
    atomic=(kind=='quest' and index in [9,18,19,20])
    if atomic:
        if add:
            if old and old!=operand:raise ValueError(f'Conflicting atomic field {kind}:{index}')
            return deepcopy(operand)
        return {} if old==operand else old
    if grouped:
        result=deepcopy(old or {})
        for group,values in operand.items():
            if kind=='quest' and index==10 and group==4:
                if add:
                    if result.get(group) and result[group]!=values:raise ValueError('Conflicting reputation objective')
                    result[group]=deepcopy(values)
                elif result.get(group)==values:result.pop(group,None)
            else:result[group]=listop(result.get(group),values,add)
        return result
    return listop(old,operand,add)
def apply_provider(path,kind,origin,method='Load'):
    s=source(path,origin)
    lua.execute(s)
    module=modules[re.search(r'CreateModule\("([^"]+)"\)',s).group(1)]
    fixes=module[method](module)
    for rid,fields in fixes.items():
        row=data[kind][rid]
        if row is None:row=lua.table();data[kind][rid]=row
        for key,value in sorted(fields.items()):
            if not isinstance(key,(int,float)):raise ValueError(f'Unresolved enum {path.name}:{rid}:{key}')
            index=key+1000 if key<0 else key-1000 if key>1000 else key
            if key<0 or key>1000:row[index]=to_lua(operate(kind,index,unlua(row[index]),unlua(value),key>1000))
            else:row[index]=value
            field_sources[kind][rid][index]=origin
    corrections.append({'file':str(path.relative_to(UPSTREAM)),'rows':len(list(fixes.keys())),'layer':origin})
legacy=UPSTREAM/'src/corrections/Forever/legacy'
for kind in data:
    filename=f'classic{kind.title() if kind!="npc" else "NPC"}Fixes.lua'
    apply_provider(legacy/filename,kind,'questiedb-forever-seed-correction')
apply_provider(legacy/'classicQuestReputationFixes.lua','quest','questiedb-forever-seed-correction')
apply_provider(legacy/'itemStartFixes.lua','item','questiedb-forever-seed-correction','LoadAutomaticQuestStarts')
for directory,layer in [('generated','questiedb-forever-delta'),('traces','questiedb-forever-trace'),('', 'questiedb-forever-authored')]:
    for kind in data:
        filename=(f'foreverBase{kind.title()}.lua' if directory=='generated' else f'forever{kind.title()}Traces.lua' if directory=='traces' else f'forever{kind.title() if kind!="npc" else "NPC"}Fixes.lua')
        apply_provider(UPSTREAM/'src/corrections/Forever'/directory/filename,kind,layer)

lookup={}
for kind in data:
    directory={'quest':'Quests','npc':'Npcs','object':'Objects','item':'Items'}[kind]
    path=UPSTREAM/f'l10n/Forever/lookup{directory}/zhCN.lua'
    s=source(path,'questiedb-forever-localization-seed')
    code=re.search(r'\[\[(return \{.*?)\]\]',s,re.S).group(1)
    lookup[kind]=lua.execute(code)

areas={r['ID']:r for r in db('AreaTable',ROOT/f'output/wow-cinema/index/{BUILD}-worldzh/db2')}
instances={r['ID']:r for r in db('Map',ROOT/f'output/wow-cinema/index/{BUILD}-worldzh/db2')}
sorts={-r['ID']:r.get('SortName_lang',str(r['ID'])) for r in db('QuestSort')}
maps={r['ID']:r for r in db('UiMap')}
assignments=db('UiMapAssignment')
byarea={}
bymap={}
for r in assignments:
    if r['AreaID'] and r['OrderIndex']==0: byarea[r['AreaID']]=r
    if r['OrderIndex']==0: bymap[r['UiMapID']]=r
wm=json.loads((ROOT/'talent/travel/cache/worldmap.json').read_text(encoding='utf8'))
items={r['ID']:r for r in db('ItemSparse',ENTITY_DB)}
factions={r['ID']:r.get('Name_lang','') for r in db('Faction',ENTITY_DB)}
races={r['ID']:r.get('Name_lang','') for r in db('ChrRaces')}
race_meta=[]
for rid,enum in [(1,'HUMAN'),(2,'ORC'),(3,'DWARF'),(4,'NIGHT_ELF'),(5,'UNDEAD'),(6,'TAUREN'),(7,'GNOME'),(8,'TROLL'),(9,'GOBLIN'),(95,'SKYBORNE_ALLIANCE'),(96,'SKYBORNE_HORDE')]:
    race_meta.append({'id':rid,'name':races.get(rid) or enum,'bit':int(modules.QuestieDB.raceKeys[enum])})
catalog_path=HERE/'raw/wowhead-catalog.json'
source(catalog_path,'third-party-forever-metadata')
catalog=json.loads(catalog_path.read_text(encoding='utf8'))
build_file=CLIENT.parent/'.build.info'
build_text=source(build_file,'local-client-build-evidence')
build_rows=list(csv.DictReader(build_text.splitlines(),delimiter='|'))
build_evidence=next(r for r in build_rows if r.get('Product!STRING:0')=='wow_classic_beta' and r.get('Active!DEC:1')=='1')
if build_evidence['Version!STRING:0']!=BUILD:raise ValueError('Installed client build changed; refresh the DB2 snapshots and BUILD together.')
current={q['id']:q for q in catalog['rows']}
detail_path=HERE/'raw/wowhead-details.json'
source(detail_path,'third-party-forever-detail-facts')
details={int(k):v for k,v in json.loads(detail_path.read_text(encoding='utf8')).items() if 'meta' in v}
current_entities={}
for d in details.values():
    for key,fields in d['entities'].items():current_entities.setdefault(key,{}).update(fields)
inventory={r['ID'] for r in db('QuestV2')}
observed={}
for path in (CLIENT/'WTF/Account').glob('*/SavedVariables/Questie.lua'):
    s=source(path,'local-game-observation')
    # Evaluate only the factual observation store, never player progress/settings.
    m=re.search(r'^QuestieForeverDB\s*=\s*\{',s,re.M)
    if m:
        start=m.end()-1
        store=lua.execute('return '+s[start:table_end(s,start)])
        for qid,q in store['quests'].items():
            if isinstance(q['title'],str): observed[qid]=q


def name(kind,rid):
    live=current_entities.get(f'{kind}:{rid}',{}).get('name_zhcn')
    if live and not live.startswith('['):return live
    translated=lookup[kind][rid] if lookup[kind] is not None else None
    if lua_type(translated)=='table': translated=translated[1]
    if kind=='item' and rid in items:
        translated=items[rid].get('Display_lang') or translated
    base=data[kind][rid]
    if kind!='item' and base and base[1]!=seed_names[kind].get(rid) and seed_names[kind].get(rid):translated=None
    return translated or (base[1] if base else None) or f'{kind} #{rid}'


def area_name(z):
    return areas.get(z,{}).get('AreaName_lang') or sorts.get(z) or maps.get(z,{}).get('Name_lang') or f'区域 #{z}'


def world(cont,wx,wy):
    off=wm['offsets'].get(str(cont))
    if not off:return None
    return [round((32-wy/(1600/3)+off[0])*256,2),round((32-wx/(1600/3)+off[1])*256,2)]


def coord(zone,x,y):
    z=zone
    while z not in byarea and areas.get(z,{}).get('ParentAreaID'):
        z=areas[z]['ParentAreaID']
    a=byarea.get(z)
    result={'zone':zone,'x':x,'y':y}
    if not a:return result
    r=a['Region']
    result['mapId']=a['UiMapID']
    result['world']=world(a['MapID'],r[3]-(r[3]-r[0])*y/100,r[4]-(r[4]-r[1])*x/100)
    return result


entities={}


def entity(kind,rid):
    key=f'{kind}:{rid}'
    if key in entities:return key
    row=data[kind][rid]
    e={'id':rid,'kind':kind,'name':name(kind,rid),'nameEn':row[1] if row else '', 'positions':[], 'instanceZones':[],
       'source':field_sources[kind][rid].get(7 if kind=='npc' else 4,'questiedb-forever-coordinate-seed'),
       'fieldSources':field_sources[kind][rid]}
    live=current_entities.get(key,{})
    if live.get('icon'):e['icon']=live['icon']
    if live.get('jsonequip'):e['stats']=live['jsonequip']
    entities[key]=e
    if row and kind in ['npc','object']:
        spawns=row[7 if kind=='npc' else 4]
        if lua_type(spawns)=='table':
            for zone,points in spawns.items():
                for p in arr(points):
                    if p[1]==-1 and p[2]==-1:e['instanceZones'].append(zone);continue
                    if isinstance(p[1],(int,float)) and isinstance(p[2],(int,float)) and 0<=p[1]<=100 and 0<=p[2]<=100:
                        e['positions'].append(coord(zone,p[1],p[2]))
        if kind=='npc':e.update(level=[row[4],row[5]],rank=row[6])
    if kind=='item':
        e['source']='client-name+questiedb-forever-sources'
        if row:
            e['drops']=[entity(k,i) for ix,k in [(2,'npc'),(3,'object')] for i in arr(row[ix])]
            e['vendors']=[entity('npc',i) for i in arr(row[14])]
            e['startsQuest']=row[5]
        item=items.get(rid,{})
        e['itemLevel']=item.get('ItemLevel',row[9] if row else None)
        e['requiredLevel']=item.get('RequiredLevel',row[10] if row else None)
        e['quality']=item.get('OverallQualityID')
    return key


quests={}
for qid in sorted(inventory|set(current)|set(observed)|set(data['quest'].keys())):
    row=data['quest'][qid]
    wh=current.get(qid)
    obs=observed.get(qid)
    detail=details.get(qid)
    q={'id':qid,'name':name('quest',qid),'nameEn':wh['name'] if wh else row[1] if row else '',
       'indexed':qid in inventory,'listed':wh is not None,'observed':obs is not None,
       'level':wh['level'] if wh else row[5] if row else None,
       'minLevel':wh['reqlevel'] if wh else row[4] if row else None,
       'zone':wh['category'] if wh else row[17] if row else None,
       'classMask':wh.get('reqclass',0) if wh else row[7] or 0 if row else 0,
       'raceMask':int(row[6] or 0) if row else None,
       'side':wh['side'] if wh else (1 if row[6] and int(row[6])&4294967373 and not int(row[6])&8589934770 else 2 if row[6] and int(row[6])&8589934770 and not int(row[6])&4294967373 else 3) if row else None,
       'type':wh['type'] if wh else None,
       'change':wh.get('envChange',{}).get('status','unknown') if wh else 'unknown',
       'changes':wh.get('envChange',{}).get('labels',[]) if wh else [],
       'starts':[], 'ends':[], 'objectives':[], 'all':[], 'any':[], 'next':[], 'exclusive':[], 'breadcrumbs':[],
       'rewards':None, 'texts':[], 'positions':[]}
    q['placeholder']=bool(re.search(r'^(?:<[^>]+>|\[(?:UNUSED|nyi|TEST|PH)\]|(?:UNUSED|nyi|TEST\b))|deprecated',q['nameEn'],re.I))
    if row:
        translated=lookup['quest'][qid]
        fresh_text=field_sources['quest'][qid].get(8,'') in ['questiedb-forever-authored','questiedb-forever-trace','questiedb-forever-delta']
        q['texts']=arr(row[8]) if fresh_text else arr(translated[2]) if translated and translated[2] else arr(row[8])
        q['textLocale']='zhCN' if any(re.search('[\u4e00-\u9fff]',t) for t in q['texts'] if isinstance(t,str)) else 'enUS'
        q['textSource']=field_sources['quest'][qid].get(8,'questiedb-forever-seed')
        for key,ix in [('starts',2),('ends',3)]:
            for j,kind in [(1,'npc'),(2,'object'),(3,'item')]:
                q[key].extend(entity(kind,i) for i in arr(row[ix][j] if row[ix] else None))
        for j,kind in [(1,'npc'),(2,'object'),(3,'item')]:
            for o in arr(row[10][j] if row[10] else None):
                q['objectives'].append({'entity':entity(kind,o[1]),'text':o[2] if isinstance(o[2],str) else None})
        for o in arr(row[10][5] if row[10] else None):
            for npc in arr(o[1]):q['objectives'].append({'entity':entity('npc',npc),'text':o[3] if isinstance(o[3],str) else None,'kind':'kill-credit'})
        q['spellObjectives']=[{'spell':o[1],'text':o[2],'item':entity('item',o[3]) if o[3] else None} for o in arr(row[10][6] if row[10] else None)]
        q['reputationObjective']=plain(row[10][4] if row[10] else None)
        q['all']=arr(row[12]);q['any']=arr(row[13]);q['exclusive']=arr(row[16]);q['breadcrumbs']=arr(row[28])
        q['parentActive']=row[25];q['requiredSkill']=plain(row[18]);q['requiredMinRep']=plain(row[19]);q['requiredMaxRep']=plain(row[20])
        q['availableStartingWith']=row[34];q['availableUntilCompleted']=row[33];q['disabledByQuest']=row[36]
        q['supersededBy']=row[22];q['requiredRanks']=plain(row[35]);q['questFlags']=row[23]
        q['requiredSpell']=row[30];q['requiredSpecialization']=row[31];q['requiredSourceItems']=[entity('item',i) for i in arr(row[21])]
        q['maxLevel']=row[32];q['repeatable']=bool((row[24] or 0)&1)
        q['breadcrumbFor']=row[27]
        q['fieldSources']=field_sources['quest'][qid]
        q['relationSource']='questiedb-forever' if any(field_sources['quest'][qid].get(i,'') in ['questiedb-forever-authored','questiedb-forever-trace','questiedb-forever-delta'] for i in [12,13]) else 'classic'
        q['locationSource']='questiedb-forever' if any(field_sources['quest'][qid].get(i,'') in ['questiedb-forever-authored','questiedb-forever-trace','questiedb-forever-delta'] for i in [2,3]) else 'questiedb-forever-seed'
        q['sourceItem']=entity('item',row[11]) if row[11] else None
        q['extraObjectives']=plain(row[29])
        if row[9]:
            q['completionTrigger']=row[9][1]
            for zone,points in (row[9][2].items() if row[9][2] else []):
                for p in arr(points):
                    if 0<=p[1]<=100 and 0<=p[2]<=100:
                        point=coord(zone,p[1],p[2]);point.update(role='poi',label=row[9][1],source='questiedb-forever-trigger');q['positions'].append(point)
        for extra in arr(row[29]):
            for zone,points in (extra[1].items() if lua_type(extra[1])=='table' else []):
                for p in arr(points):
                    if 0<=p[1]<=100 and 0<=p[2]<=100:
                        point=coord(zone,p[1],p[2]);point.update(role='poi',label=extra[3] or '额外目标',source='questiedb-forever-extra');q['positions'].append(point)
    if wh:
        if not row: q['name']=wh['name']
        q['rewards']={'fixed':[{'entity':entity('item',i),'count':n} for i,n in wh.get('itemrewards',[])],
                      'choice':[{'entity':entity('item',i),'count':n} for i,n in wh.get('itemchoices',[])],
                      'xp':wh.get('xp'),'money':wh.get('money'), 'reputation':wh.get('reprewards',[]),'source':'wowhead-forever'}
    if detail:
        q['detailSource']=detail['source'];q['currentPoints']=[]
        live=detail['meta']
        if live.get('races'):q['raceMask']=live['races']
        for p in detail['positions']:
            kind,rid=p['entity'].split(':');key=entity(kind,int(rid))
            if p['role']=='start' and key not in q['starts']:q['starts'].append(key)
            if p['role']=='end' and key not in q['ends']:q['ends'].append(key)
            for x,y,*_ in p['coords']:
                if 0<=x<=100 and 0<=y<=100:
                    point=coord(p['zone'],x,y);point.update(entity=key,role=p['role'],floor=p['floor'],source='wowhead-forever')
                    # Floor coordinates are not projected onto the outdoor frame.
                    if p['floor']>0:point.pop('world',None)
                    q['currentPoints'].append(point)
        if q['currentPoints']:q['locationSource']='wowhead-forever'
    if obs:
        q['name']=obs['title'];q['level']=obs['level'] or q['level']
        def clean_objective(o):
            text=re.sub(r'\s*[:：]?\s*\d+\s*/\s*\d+\s*$','',o['text'])
            return text+(f'（需要 {int(o["numRequired"])}）' if o['numRequired'] and o['numRequired']>0 else '')
        q['observedTexts']=[clean_objective(o) for o in arr(obs['objectives']) if isinstance(o['text'],str)]
        q['observedObjectiveDetails']=[{'text':clean_objective(o),'type':o['type'],'numRequired':o['numRequired']} for o in arr(obs['objectives']) if isinstance(o['text'],str)]
        for point in arr(obs['mapPOIs']):
            if isinstance(point['x'],(float,int)) and isinstance(point['y'],(float,int)):
                a=bymap.get(point['mapID']);r=a['Region'] if a else None
                q['positions'].append({'mapId':point['mapID'],'x':point['x']*100,'y':point['y']*100,
                    'role':'start' if point['isQuestStart'] else 'poi',
                    'world':world(a['MapID'],r[3]-(r[3]-r[0])*point['y'],r[4]-(r[4]-r[1])*point['x']) if a else None})
    quests[qid]=q

# A chain's next edge comes from an actual predecessor requirement, never inferred
# from similarly named quests or optional breadcrumbs.
for q in quests.values():
    for rid in set(abs(x) for x in q['all']+q['any']):
        if rid in quests: quests[rid]['next'].append(q['id'])

blobs={r['ID']:r for r in db('QuestPOIBlob')}
for p in db('QuestPOIPoint'):
    b=blobs[p['QuestPOIBlobID']]
    q=quests.get(b['QuestID'])
    if q:q['positions'].append({'mapId':b['UiMapID'],'world':world(b['MapID'],p['X'],p['Y']),
                                'role':'turnin' if b['ObjectiveIndex']==-1 else 'poi','source':'client-db2'})

zoneids=set(q['zone'] for q in quests.values() if q['zone'] is not None)
zoneids.update(p['zone'] for e in entities.values() for p in e['positions'])
zoneids.update(z for e in entities.values() for z in e['instanceZones'])
zoneids.update(p['zone'] for q in quests.values() for p in q.get('currentPoints',[]))
zones={z:{'id':z,'name':area_name(z),'mapId':byarea.get(z,{}).get('UiMapID'),
          'dungeon':instances.get(areas.get(z,{}).get('ContinentID'),{}).get('InstanceType') in [1,2],
          'instanceMap':areas.get(z,{}).get('ContinentID')} for z in zoneids}
for q in quests.values():
    instance_zones=set()
    if zones.get(q['zone'],{}).get('dungeon'):instance_zones.add(q['zone'])
    for objective in q['objectives']:
        e=entities[objective['entity']]
        for target in [e]+[entities[k] for k in e.get('drops',[])]:
            instance_zones.update(z for z in target['instanceZones'] if zones.get(z,{}).get('dungeon'))
            for p in target['positions']:
                if zones.get(p['zone'],{}).get('dungeon'):instance_zones.add(p['zone'])
    q['dungeons']=sorted(instance_zones)
meta={'schemaVersion':1,'build':BUILD,'product':'wow_classic_beta','updatedAt':datetime.now(timezone.utc).isoformat(),
      'clientQuestIds':len(inventory),'namedQuests':sum(not q['name'].startswith('quest #') for q in quests.values()),
      'foreverListed':len(current),'observed':len(observed),'classicQuests':len(list(data['quest'].keys())),
      'changes':dict(Counter(q['change'] for q in quests.values() if q['listed'])),
      'corrections':corrections,
      'coverage':{'rewards':sum(q['rewards'] is not None for q in quests.values()),
                  'relations':sum(bool(q['all'] or q['any'] or q['next']) for q in quests.values()),
                  'foreverRelations':sum(q.get('relationSource')=='questiedb-forever' for q in quests.values()),
                  'foreverDetails':len(details),
                  'chineseTitles':sum(bool(re.search('[\u4e00-\u9fff]',q['name'])) for q in quests.values()),
                  'startCoordinates':sum(any(entities[e]['positions'] for e in q['starts']) for q in quests.values()),
                  'indexOnly':sum(q['name'].startswith('quest #') for q in quests.values()),
                  'placeholders':sum(q['listed'] and q['placeholder'] for q in quests.values())}}
for label,predicate in [('publicChinese',lambda q:bool(re.search('[\u4e00-\u9fff]',q['name']))),('publicRelations',lambda q:bool(q['all'] or q['any'] or q['next'])),('publicStartCoordinates',lambda q:any(entities[e]['positions'] for e in q['starts']))]:
    meta['coverage'][label]=sum(q['listed'] and predicate(q) for q in quests.values())
meta['clientEvidence']={'product':build_evidence['Product!STRING:0'],'version':build_evidence['Version!STRING:0'],'locale':'zhCN','localeMask':64}
OUT.mkdir(parents=True,exist_ok=True)
index=[]
chunks=defaultdict(dict)
for q in quests.values():
    e=[entities[k]['name'] for k in q['starts']+q['ends']]
    rewards=q['rewards']
    start_locations=[]
    for key in q['starts']:
        points=[p for p in q.get('currentPoints',[]) if p['entity']==key and p['role']=='start'] or entities[key]['positions']
        if points:
            p=points[0];start_locations.append({'name':entities[key]['name'],'zone':p['zone'],'x':p['x'],'y':p['y']})
    index.append({k:q.get(k) for k in ['id','name','nameEn','level','minLevel','zone','side','type','classMask','raceMask','change','listed','observed','indexed','dungeons','placeholder']}
                 | {'search':' '.join(e+[entities[x['entity']]['name'] for x in (rewards['choice']+rewards['fixed'] if rewards else [])]),
                    'starterNames':[entities[k]['name'] for k in q['starts']],'startLocations':start_locations,
                    'hasRewards':rewards is not None,'hasChain':bool(q['all'] or q['any'] or q['next']),
                    'xp':rewards['xp'] if rewards else None,'money':rewards['money'] if rewards else None})
    chunks[q['id']//256][q['id']]=q
for chunk,rows in chunks.items():
    (OUT/f'detail-{chunk}.js').write_text(f'window.FOREVER_QUEST_CHUNKS[{chunk}]='+json.dumps(rows,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf8')
(OUT/'catalog.js').write_text('window.FOREVER_QUESTS='+json.dumps({'meta':meta,'zones':zones,'factions':factions,'races':race_meta,'quests':index,
                         'worldmap':{k:wm[k] for k in ['Z','grid','offsets','tiles','dungeons']}},ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf8')
entity_chunks=defaultdict(dict)
for key,e in entities.items():entity_chunks[f'{e["kind"]}-{e["id"]//2048}'][key]=e
for chunk,rows in entity_chunks.items():
    (OUT/f'entity-{chunk}.js').write_text('window.FOREVER_QUEST_ENTITIES=window.FOREVER_QUEST_ENTITIES||{};Object.assign(window.FOREVER_QUEST_ENTITIES,'+json.dumps(rows,ensure_ascii=False,separators=(',',':'))+');\n',encoding='utf8')
if (OUT/'entities.js').exists():(OUT/'entities.js').unlink()
(HERE/'catalog-full.json').write_text(json.dumps({'meta':meta,'zones':zones,'quests':quests,'entities':entities},ensure_ascii=False),encoding='utf8')
manifest={'meta':meta,'questieDBSnapshot':json.loads((UPSTREAM/'snapshot.json').read_text()),'sources':sources,'remoteResponses':catalog['responses'],'knownLimitations':[
    'QuestV2 IDs do not prove playable availability. Index-only entries are hidden by default.',
    'Forever coordinate seed preserves inherited world positions; it does not detect moved content. Static correction layers are pinned; player-specific dynamic corrections are not flattened.',
    'Inherited prerequisite fields remain historical references unless specifically updated; an absent prerequisite is not proof that none exists.',
    'A changed Forever quest can retain its ID while its objectives, races, prerequisites and locations change.',
    'Forever observations override only fields actually observed, and no player progress is published.',
    'Rewards are public Forever metadata, not locally verified reward offers.',
    'XP listed is the database base value; character level and server hotfixes can change the actual award.',
    'New quest translations and complete server-side prerequisite/reward offers are not all available.',
    '239 current detail pages were captured before HTTP 403; repeated requests were stopped, not bypassed.',
    'QuestLine order is a narrative ordering; it is not treated as a mandatory prerequisite.']}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
missing=[]
for q in quests.values():
    if not q['listed'] or q['placeholder']:continue
    gaps=[]
    if not q['starts']:gaps.append('接取对象')
    if not q['texts'] and not q.get('observedTexts'):gaps.append('目标文字')
    if not re.search('[\u4e00-\u9fff]',q['name']):gaps.append('中文名称')
    if q['change'] in ['new','updated'] and q.get('relationSource')!='questiedb-forever':gaps.append('无限前置条件核验')
    if gaps:missing.append({'id':q['id'],'name':q['name'],'change':q['change'],'missing':gaps})
(HERE/'missing-fields.json').write_text(json.dumps(missing,ensure_ascii=False,indent=2),encoding='utf8')
source_out=OUT/'source';source_out.mkdir(exist_ok=True)
for filename in ['build_catalog.py','fetch_catalog.py','fetch_details.py','fetch_questiedb.py','fetch_vendor.py','README.md']:
    if (HERE/filename).exists():(source_out/filename).write_bytes((HERE/filename).read_bytes())
for filename in ['quest-model.js','quest-views.js','quests.css']:
    (source_out/filename).write_bytes((ROOT/'talent/tier-model/ui'/filename).read_bytes())
print(json.dumps(meta,ensure_ascii=False,indent=2))
