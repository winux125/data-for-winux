"""Offline search across the expanded official library; document citations, no automatic rule activation."""
import hashlib
import json
from pathlib import Path
import threading
from types import SimpleNamespace
from .bm25 import BM25Index,Lexicon
from .units import PARSER_VERSION,parse_document
from .paths import CORPUS_DIR

DEFAULT_LIBRARY=CORPUS_DIR/'legal_corpus_v3/manifest.json'
DEFAULT_ROLES={'operational','background'}


def sha(data):return hashlib.sha256(data).hexdigest()


def line_spans(lines,budget=3000,overlap=2):
    """Whole-line overlapping spans; never fabricate a clause number or drop a long line."""
    start=0
    while start<len(lines):
        end=start;size=0
        while end<len(lines) and (end==start or size+len(lines[end])+1<=budget):
            size+=len(lines[end])+1;end+=1
        yield start+1,end
        if end==len(lines):break
        start=max(start+1,end-overlap)


class SourceLibrary:
    def __init__(self,path=DEFAULT_LIBRARY):
        self.path=Path(path).resolve();self.root=self.path.parent
        self.manifest=json.loads(self.path.read_text(encoding='utf-8'))
        if self.manifest.get('jurisdiction')!='KZ':raise ValueError('Unexpected library jurisdiction')
        self.sources={};self.chunks={};self.lines={};self.by_source={};self._indices={}
        self.units={};self.structures={}
        self.structure_nodes={}
        self._index_lock=threading.Lock()  # concurrent first queries must build each role index once
        for source in self.manifest['sources']:
            code=source['source_id']
            if code in self.sources:raise ValueError('Duplicate source')
            for kind in ('snapshot','text'):
                target=(self.root/source[kind+'_path']).resolve()
                if not target.is_relative_to(self.root) or sha(target.read_bytes())!=source[kind+'_sha256']:
                    raise ValueError('Source path/hash mismatch: '+code)
            lines=(self.root/source['text_path']).read_text(encoding='utf-8').splitlines()
            self.sources[code]=source;self.lines[code]=lines;self.by_source[code]=[]
            # Structural parent units and child chunks; exact line ranges only where structure is unreliable.
            structure=parse_document(code,lines,source['role']);self.structures[code]=structure
            document_id=f'{code}:document'
            self.structure_nodes[document_id]=dict(node_id=document_id,kind='document',parent_id=None,title=source['title'])
            for unit in structure.units:
                container_id=f'{code}:{unit.container}:container'
                self.structure_nodes.setdefault(container_id,dict(node_id=container_id,kind='container',
                                                                  parent_id=document_id,title=unit.container))
                path=[document_id,container_id]
                for i,heading in enumerate(unit.headings):
                    key=sha('\n'.join(unit.headings[:i+1]).encode())[:20]
                    node_id=f'{code}:{unit.container}:heading:{key}'
                    self.structure_nodes.setdefault(node_id,dict(node_id=node_id,kind='heading',parent_id=path[-1],title=heading))
                    path.append(node_id)
                unit.parent_id=path[-1];unit.structural_path=path+[unit.unit_id]
                self.units[unit.unit_id]=unit
            for chunk in structure.chunks:
                self.chunks[chunk.chunk_id]=dict(chunk_id=chunk.chunk_id,source_id=code,lines=list(chunk.lines),
                    text=chunk.text,text_sha256=chunk.text_sha256,unit_id=chunk.unit_id,part=chunk.part,
                    search_text=chunk.search_text,search_sha256=chunk.search_sha256,parent_sha256=chunk.parent_sha256)
                self.by_source[code].append(chunk.chunk_id)

    def _index(self,roles,lexicon=True):
        key=(tuple(sorted(roles)),bool(lexicon))
        index=self._indices.get(key)
        if index is not None:return index
        with self._index_lock:
            if key not in self._indices:self._indices[key]=self._build_index(roles,lexicon)
            return self._indices[key]

    def _build_index(self,roles,lexicon=True):
        clauses={};sections={}
        for cid,chunk in self.chunks.items():
            source=self.sources[chunk['source_id']];unit=self.units[chunk['unit_id']]
            if source['role'] not in roles or not unit.indexed:continue
            if source['role']!='guidance' and source.get('official_in_force') is not True and source['role']!='historical_reference':continue
            # Headings are already in the child's search text; no document title in an editorial field.
            sections[unit.unit_id]=dict(short_title='',seek='')
            clauses[cid]=SimpleNamespace(source_id=source['source_id'],section_id=unit.unit_id,text=chunk['search_text'],
                headings=(),subitems=(),status=unit.status)
        corpus=SimpleNamespace(clauses=clauses,brief=SimpleNamespace(sections=sections))
        return BM25Index(corpus,Lexicon() if lexicon else None)

    def search(self,text,k=5,predicates=(),include_context=False,include_guidance=False,include_historical=False,source_ids=None,lexicon=True):
        if not 1<=k<=50:raise ValueError('k outside 1..50')
        roles=DEFAULT_ROLES.copy()
        if include_context:roles|={'amendment','reference_only'}
        if include_guidance:roles.add('guidance')
        if include_historical:roles.add('historical_reference')
        # Children are retrieved; repeated children of one parent unit collapse onto its best child.
        hits=self._index(roles,lexicon).search(text,k=min(200,k*8),predicates=predicates,source_ids=source_ids)
        result,seen_units=[],{}
        for hit in hits:
            chunk=self.chunks[hit.clause_id];source=self.sources[chunk['source_id']];unit=self.units[chunk['unit_id']]
            if unit.unit_id in seen_units:
                seen_units[unit.unit_id]['also_matched_chunks'].append(hit.clause_id);continue
            item=dict(chunk_id=hit.clause_id,rank=len(result)+1,score=hit.score,source_id=chunk['source_id'],
                title=source['title'],official_url=source['official_url'],role=source['role'],scope=source['scope'],
                lines=chunk['lines'],text=chunk['text'],text_sha256=chunk['text_sha256'],source_text_sha256=source['text_sha256'],
                official_in_force=source.get('official_in_force'),unit_id=unit.unit_id,unit_kind=unit.kind,
                unit_label=unit.label,unit_lines=list(unit.lines),unit_status=unit.status,container=unit.container,
                headings=list(unit.headings),structure=unit.structure,numbering_anomaly=unit.numbering_anomaly,
                citation_granularity=unit.citation_level,also_matched_chunks=[],
                applicability_verified=False,legal_verdict_enabled=False)
            seen_units[unit.unit_id]=item;result.append(item)
            if len(result)==k:break
        return result

    def packet(self,chunk_ids,budget_chars=24000,neighbors=1):
        """Legacy adjacency packet (child + neighbouring chunks) for diagnostics only.

        It does NOT restore whole parent norms; generator input comes from
        LegalRAG.packet_sources / source_packet.SourcePacketBuilder.
        """
        if not chunk_ids or len(chunk_ids)!=len(set(chunk_ids)) or any(cid not in self.chunks for cid in chunk_ids):
            raise ValueError('Unknown/empty/duplicate source chunks')
        if not 1000<=budget_chars<=100000 or neighbors not in (0,1,2):raise ValueError('Packet budget/context outside range')
        candidates=list(chunk_ids)
        for cid in chunk_ids:
            source=self.chunks[cid]['source_id'];group=self.by_source[source];i=group.index(cid)
            candidates += [other for other in group[max(0,i-neighbors):i+neighbors+1] if other not in candidates]
        packet=dict(schema_version=1,citation_granularity='document',items=[],omitted=[],
            budget_chars=budget_chars,applicability_verified=False,legal_verdict_enabled=False,
            limitations=['Source spans are not reviewed rule cards. Verify conditions, exceptions, linked acts and event date.'])
        for cid in candidates:
            chunk=self.chunks[cid];source=self.sources[chunk['source_id']]
            item=dict({key:value for key,value in chunk.items() if key!='search_text'},
                reason='retrieved' if cid in chunk_ids else 'adjacent_source_context',title=source['title'],
                official_url=source['official_url'],role=source['role'],scope=source['scope'],
                official_in_force=source.get('official_in_force'),raw_revision_value=source.get('raw_revision_value'),
                source_text_sha256=source['text_sha256'],linked_source_ids=source.get('linked_source_ids',[]))
            packet['items'].append(item)
            if len(json.dumps(packet,ensure_ascii=False))>budget_chars:
                packet['items'].pop()
                if cid==chunk_ids[0]:raise ValueError('Primary source span exceeds packet budget; increase budget')
                packet['omitted'].append(dict(chunk_id=cid,reason='budget'))
        packet['serialized_chars']=0
        def measure():
            for _ in range(5):
                size=len(json.dumps(packet,ensure_ascii=False))
                if size==packet['serialized_chars']:return size
                packet['serialized_chars']=size
            raise ValueError('Unstable serialized character count')
        while measure()>budget_chars:
            if len(packet['items'])==1:raise ValueError('Primary source and omission metadata exceed packet budget')
            removed=packet['items'].pop()
            packet['omitted'].append(dict(chunk_id=removed['chunk_id'],reason='budget_including_metadata'))
        return packet

    def summary(self):
        from collections import Counter
        return dict(library_id=self.manifest['library_id'],sources=len(self.sources),chunks=len(self.chunks),
            roles=dict(Counter(s['role'] for s in self.sources.values())),source_hashes_verified=True,
            parser_version=PARSER_VERSION,units=len(self.units),
            structure=dict(Counter(c['structure'] for d in self.structures.values() for c in d.containers)),
            manifest_sha256=sha(self.path.read_bytes()),network_required=False,legal_verdict_enabled=False)
