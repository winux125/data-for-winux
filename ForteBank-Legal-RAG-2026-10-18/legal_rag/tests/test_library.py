import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from legal_rag.library import SourceLibrary,line_spans,DEFAULT_LIBRARY
from legal_rag.collect_sources import Links
from legal_rag import LegalRAG


class ExpandedLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.library=SourceLibrary()

    def test_full_source_line_coverage_and_exact_spans(self):
        library=self.library
        self.assertGreaterEqual(len(library.sources),23)
        self.assertEqual({s['jurisdiction'] for s in library.sources.values()},{'KZ'})
        for code,lines in library.lines.items():
            covered=set()
            for cid in library.by_source[code]:
                chunk=library.chunks[cid];a,b=chunk['lines'];covered.update(range(a,b+1))
                exact='\n'.join(lines[a-1:b])+'\n'
                self.assertEqual(chunk['text'],exact)
                self.assertEqual(chunk['text_sha256'],hashlib.sha256(exact.encode()).hexdigest())
            self.assertEqual(covered,set(range(1,len(lines)+1)))

    def test_long_line_survives_without_fabricated_clause(self):
        lines=['short','x'*9000,'last']
        spans=list(line_spans(lines,budget=3000))
        self.assertTrue(any(a<=2<=b for a,b in spans))
        self.assertEqual(sorted(set(i for a,b in spans for i in range(a,b+1))),[1,2,3])

    def test_default_retrieval_excludes_history_central_bank_and_guidance(self):
        index=self.library._index({'operational','background'})
        codes={c.source_id for c in index.corpus.clauses.values()}
        self.assertNotIn('V1700015541',codes)
        self.assertNotIn('Z950002444_',codes)
        self.assertNotIn('V2000021299',codes)
        self.assertNotIn('NBK-news-17656',codes)
        self.assertIn('V2600038748',codes)

    def test_guidance_is_explicit_and_never_an_active_verdict_rule(self):
        hits=self.library.search('наличной иностранной валюты',k=2,include_guidance=True,source_ids={'NBK-news-17656'})
        self.assertTrue(hits)
        self.assertEqual(hits[0]['role'],'guidance')
        self.assertFalse(hits[0]['legal_verdict_enabled'])
        self.assertFalse(hits[0]['applicability_verified'])
        self.assertEqual(hits[0]['citation_granularity'],'document')

    def test_packet_keeps_primary_exact_quote_and_enforces_serialized_budget(self):
        cid=self.library.by_source['V1900019680'][2]
        packet=self.library.packet([cid],budget_chars=6500,neighbors=2)
        self.assertEqual(packet['items'][0]['chunk_id'],cid)
        self.assertEqual(packet['items'][0]['text'],self.library.chunks[cid]['text'])
        self.assertEqual(packet['serialized_chars'],len(json.dumps(packet,ensure_ascii=False)))
        self.assertLessEqual(packet['serialized_chars'],6500)
        self.assertTrue(packet['omitted'])

    def test_modified_source_is_rejected(self):
        source=copy.deepcopy(next(iter(self.library.sources.values())))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'sources').mkdir()
            for kind in ('snapshot','text'):
                shutil.copyfile(DEFAULT_LIBRARY.parent/source[kind+'_path'],root/source[kind+'_path'])
            (root/source['text_path']).write_text('tampered',encoding='utf-8')
            manifest=dict(jurisdiction='KZ',sources=[source])
            (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            with self.assertRaises(ValueError):SourceLibrary(root/'manifest.json')

    def test_explicit_previous_version_remains_available_and_unchanged(self):
        previous=DEFAULT_LIBRARY.parents[1]/'legal_corpus_v2/manifest.json'
        proof=json.loads(previous.with_name('verification.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(previous.read_bytes()).hexdigest(),proof['manifest_sha256'])
        self.assertEqual(LegalRAG(source_library_path=previous).source_library().summary()['sources'],25)
        self.assertGreater(self.library.summary()['sources'],25)

    def test_concurrent_first_queries_build_each_role_index_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from unittest import mock
        import legal_rag.library as module
        library=SourceLibrary()
        built=[]
        real=module.BM25Index
        def counting(*args,**kwargs):
            built.append(1);return real(*args,**kwargs)
        with mock.patch.object(module,'BM25Index',counting),ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:[h['chunk_id'] for h in library.search('кассир ушёл с рабочего места',k=5)],range(8)))
        self.assertEqual(len(built),1)
        self.assertEqual(len({tuple(r) for r in results}),1)

    def test_reference_parser_keeps_alphanumeric_adilet_ids_and_rejects_other_hosts(self):
        parser=Links();parser.feed('<a href="/rus/docs/V14E0010212">bank</a><a href="https://adilet.zan.kz/rus/docs/Z1300000073/links">id</a><a href="https://example.org/rus/docs/Z990000416_">other</a>')
        self.assertEqual(parser.targets,{'V14E0010212','Z1300000073'})
