"""Download public official KZ texts into a versioned library, preserving the frozen CV bundle."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
from urllib.error import URLError,HTTPError
from urllib.parse import urlparse
from urllib.request import Request,urlopen
from html.parser import HTMLParser
from .source_fetch import Text,request
from .paths import CORE_DIR

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_OUT=ROOT/'data/legal_corpus_v3'
CATALOG=Path(__file__).with_name('data')/'source_catalog_v3.json'


def digest(data):return hashlib.sha256(data).hexdigest()


def save(path,value):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)


class Links(HTMLParser):
    def __init__(self):super().__init__();self.targets=set()
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            href=dict(attrs).get('href','')
            parsed=urlparse(href)
            if parsed.netloc and parsed.hostname not in ('adilet.zan.kz','www.adilet.zan.kz','old.adilet.zan.kz'):return
            match=re.search(r'/(?:rus|kaz|eng)/docs/([A-Z][A-Za-z0-9_]{7,16})(?=/|$)',parsed.path)
            if match:self.targets.add(match.group(1))


class NewsBody(HTMLParser):
    VOID={'br','hr','img','input','meta','link','source','wbr','area','base','embed','param','track','col'}
    def __init__(self):
        super().__init__();self.body=Text();self.depth=0;self.roots=0;self.title=None;self.published=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='meta':
            key=attrs.get('property') or attrs.get('name')
            if key=='og:title':self.title=attrs.get('content')
            if key in ('article:published_time','datePublished'):self.published=attrs.get('content')
        if not self.depth:
            if tag=='div' and 'post__content-text' in attrs.get('class','').split():self.depth=1;self.roots+=1
        else:
            if tag not in self.VOID:self.depth+=1
            self.body.handle_starttag(tag,list(attrs.items()))
    def handle_endtag(self,tag):
        if self.depth:
            if tag not in self.VOID:self.depth-=1
            self.body.handle_endtag(tag)
    def handle_data(self,data):
        if self.depth:self.body.handle_data(data)


def fetch_page(row,out):
    code=row['source_id'];record_path=out/'records'/(code+'.json')
    if record_path.exists():
        old=json.loads(record_path.read_text(encoding='utf-8'))
        for kind in ('snapshot','text'):
            if digest((out/old[kind+'_path']).read_bytes())!=old[kind+'_sha256']:raise ValueError('Modified news snapshot')
        return old
    url=row['url'];parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='nationalbank.kz':raise ValueError('Unexpected news source')
    req=Request(url,headers={'User-Agent':'ForteBank-official-source-library/1'})
    with urlopen(req,timeout=30) as response:
        if urlparse(response.url).hostname not in ('nationalbank.kz','www.nationalbank.kz'):raise ValueError('Unexpected news redirect')
        raw=response.read()
    parser=NewsBody();parser.feed(raw.decode('utf-8'));text=parser.body.text()
    if parser.roots!=1 or not parser.title or row['title_contains'].casefold() not in parser.title.casefold() or len(text)<500:
        raise ValueError('Cannot isolate official article body')
    snapshot=out/'sources'/(code+'.html');txt=out/'sources'/(code+'.txt')
    snapshot.write_bytes(raw);txt.write_bytes(text.encode('utf-8'))
    links=Links();links.feed(raw.decode('utf-8'))
    record=dict(row,title=parser.title,official_url=url,provider='official National Bank website',jurisdiction='KZ',
        retrieved_utc=datetime.now(timezone.utc).isoformat(),published_meta=parser.published,
        official_is_actual=None,official_in_force=None,raw_revision_field=None,raw_revision_value=None,
        snapshot_path=snapshot.relative_to(out).as_posix(),snapshot_sha256=digest(raw),
        text_path=txt.relative_to(out).as_posix(),text_sha256=digest(txt.read_bytes()),text_characters=len(text),
        linked_source_ids=sorted(links.targets),legal_verdict_enabled=False,
        applicability='dated regulator explanation; not an independent binding rule; check primary act and date')
    save(record_path,record);return record


def fetch(row,out):
    code=row['source_id'];snapshot_path=out/'sources'/(code+'.json');text_path=out/'sources'/(code+'.txt')
    meta_path=out/'records'/(code+'.json')
    if meta_path.exists():
        previous=json.loads(meta_path.read_text(encoding='utf-8'))
        if digest(snapshot_path.read_bytes())!=previous['snapshot_sha256'] or digest(text_path.read_bytes())!=previous['text_sha256']:
            raise ValueError('Existing library snapshot was modified: '+code)
        return previous
    seed_index=json.loads((CORE_DIR/'sources.json').read_text(encoding='utf-8'))
    seed=next((s for s in seed_index['sources'] if s['source_id']==code),None)
    if row.get('seed'):
        if seed is None:raise ValueError('Missing frozen seed')
        for kind in ('snapshot','text'):
            src=CORE_DIR/seed[kind+'_path']
            if digest(src.read_bytes())!=seed[kind+'_sha256']:raise ValueError('Frozen source hash mismatch')
            shutil.copyfile(src,snapshot_path if kind=='snapshot' else text_path)
        snapshot=json.loads(snapshot_path.read_text(encoding='utf-8'));meta=snapshot['metadata'];content=snapshot['content']
        retrieved=seed['retrieved_utc']
    else:
        result=request('/api/search',{'query':'','filters':{'group_number':code,'language':'rus'},'page':1,'page_size':10})
        matches=[r.get('document',r) for r in result['results']]
        matches=[m for m in matches if m.get('group_number')==code and m.get('language')=='rus' and m.get('is_actual') is True]
        alternatives=matches.copy()
        if row.get('preferred_document_id'):matches=[m for m in matches if m['id']==row['preferred_document_id']]
        if len(matches)!=1:raise ValueError('Ambiguous or missing current Russian document: '+code)
        meta=matches[0]
        if row.get('title_contains','').casefold() not in meta['title_ru'].casefold():raise ValueError('Unexpected official title: '+code)
        content=request('/api/documents/'+meta['id']+'/content')
        html=content.get('text_content') or content.get('content')
        if not isinstance(html,str) or len(html)<300:raise ValueError('Missing full legal text: '+code)
        parser=Text();parser.feed(html);text=parser.text()
        if len(text)<200:raise ValueError('Empty normalized legal text: '+code)
        snapshot=dict(metadata=meta,content=content,provider_search_alternatives=alternatives)
        snapshot_path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        text_path.write_bytes(text.encode('utf-8'));retrieved=datetime.now(timezone.utc).isoformat()
    html=content.get('text_content') or content.get('content');links=Links();links.feed(html)
    record=dict(row,title=meta['title_ru'],official_url='https://adilet.zan.kz/rus/docs/'+code,
        document_id=meta['id'],content_api_url='https://adilet.zan.kz/api/documents/'+meta['id']+'/content',
        jurisdiction='KZ',provider='official Adilet public API',official_is_actual=meta.get('is_actual'),
        official_in_force=meta.get('in_force'),raw_revision_field='end_date',raw_revision_value=meta.get('end_date'),
        retrieved_utc=retrieved,snapshot_path=snapshot_path.relative_to(out).as_posix(),
        snapshot_sha256=digest(snapshot_path.read_bytes()),text_path=text_path.relative_to(out).as_posix(),
        text_sha256=digest(text_path.read_bytes()),text_characters=len(text_path.read_text(encoding='utf-8')),
        linked_source_ids=sorted(links.targets-{code}),
        applicability='document status only; clause wording, operation, organization and event date require verification',
        legal_verdict_enabled=False)
    save(meta_path,record);return record


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=DEFAULT_OUT);p.add_argument('--catalog',type=Path,default=CATALOG)
    p.add_argument('--reuse',type=Path,help='Reuse verified files of a prior version without changing it');a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    for name in ('sources','records'):(out/name).mkdir(exist_ok=True)
    catalog=json.loads(a.catalog.read_text(encoding='utf-8'));rows=catalog['sources']+catalog.get('pages',[])
    if len({r['source_id'] for r in rows})!=len(rows):raise ValueError('Duplicate source ID')
    if any(not re.fullmatch(r'(?:[A-Z][A-Za-z0-9_]{7,24}|NBK-news-\d+)',r['source_id']) for r in rows):raise ValueError('Invalid source ID')
    if a.reuse:
        prior=a.reuse.resolve()
        for row in rows:
            previous=prior/'records'/(row['source_id']+'.json');destination=out/'records'/previous.name
            if not previous.exists() or destination.exists():continue
            record=json.loads(previous.read_text(encoding='utf-8'))
            if any(record.get(k)!=v for k,v in row.items()):raise ValueError('Catalog metadata changed; explicit review needed: '+row['source_id'])
            for kind in ('snapshot','text'):
                src=(prior/record[kind+'_path']).resolve();target=(out/record[kind+'_path']).resolve()
                if not src.is_relative_to(prior) or not target.is_relative_to(out) or digest(src.read_bytes())!=record[kind+'_sha256']:
                    raise ValueError('Prior source path/hash mismatch')
                if target.exists() and digest(target.read_bytes())!=record[kind+'_sha256']:raise ValueError('Destination source conflict')
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
            shutil.copyfile(previous,destination)
    completed=[];errors=[]
    def work(row):
        for attempt in range(3):
            try:return fetch_page(row,out) if row.get('url') else fetch(row,out)
            except (URLError,TimeoutError,ConnectionError,HTTPError):
                if attempt==2:raise
                time.sleep(2*(attempt+1))
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(work,row):row for row in rows}
        for future in as_completed(futures):
            row=futures[future]
            try:
                record=future.result();completed.append(record)
                print(json.dumps(dict(source_id=record['source_id'],status='downloaded',role=record['role'],in_force=record['official_in_force'],characters=record['text_characters'])),flush=True)
            except Exception as exc:
                errors.append(dict(source_id=row['source_id'],error=type(exc).__name__+': '+str(exc)))
                print(json.dumps(dict(source_id=row['source_id'],status='failed',error=type(exc).__name__)),flush=True)
    ids={r['source_id'] for r in completed}
    manifest=dict(schema_version=1,library_id=catalog.get('library_id','kz-banking-open-sources-2026-10-17-v2'),jurisdiction='KZ',
        created_utc=datetime.now(timezone.utc).isoformat(),catalog_sha256=digest(a.catalog.read_bytes()),
        videos_used=False,network_required_for_search=False,legal_verdict_enabled=False,
        sources=sorted(completed,key=lambda r:r['source_id']),errors=errors,
        unresolved_source_links=sorted({x for r in completed for x in r['linked_source_ids']}-ids))
    save(out/'manifest.json',manifest)
    print(json.dumps(dict(status='complete' if not errors else 'partial',sources=len(completed),new_sources=sum(not r.get('seed') for r in completed),errors=errors)),flush=True)
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
