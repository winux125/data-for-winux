"""Index provenance, tier isolation, query encoding reuse, and explicit device configuration."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from legal_rag import shared
from legal_rag.config import load_config
from legal_rag.dense import DenseIndex
from legal_rag.embed import HashEmbedder, IndexInvalid, build_index, load_index, read_npy, write_npy
from legal_rag.library import SourceLibrary
from legal_rag.retrieve import Retriever


def tiny_library(directory):
    root = Path(directory)
    text = 'Глава 1. Общее\n1. Работник пересчитывает наличные деньги.\n2. Клиент получает документы.\n'
    (root / 'text.txt').write_text(text, encoding='utf-8')
    digest = hashlib.sha256((root / 'text.txt').read_bytes()).hexdigest()
    manifest = dict(jurisdiction='KZ', library_id='fixture', sources=[dict(
        source_id='TEST', title='Fixture', official_url='https://example.test', role='operational', scope='bank',
        official_in_force=True, snapshot_path='text.txt', text_path='text.txt',
        snapshot_sha256=digest, text_sha256=digest)])
    (root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return SourceLibrary(root / 'manifest.json')


class IndexTests(unittest.TestCase):
    def test_roundtrip_manifest_and_structural_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            lib = tiny_library(temp)
            out = Path(temp) / 'index'
            embedder = HashEmbedder(16)
            manifest = build_index(lib, embedder, out)
            flat, ids, loaded = load_index(lib, out, embedder.describe())
            self.assertEqual(len(flat), 16 * len(ids))
            self.assertFalse(loaded['embedder']['is_real_model'])
            self.assertTrue((out / 'structure.json').exists())
            unit = next(u for u in lib.units.values() if u.indexed)
            self.assertIn(unit.parent_id, lib.structure_nodes)
            self.assertEqual(unit.structural_path[-1], unit.unit_id)
            self.assertEqual(json.loads((out / 'structure.json').read_text(encoding='utf-8'))['sources']['TEST']['title'], 'Fixture')
            # A vector change is rejected, not silently rebuilt.
            with (out / 'vectors.npy').open('ab') as f:
                f.write(b'x')
            with self.assertRaises(IndexInvalid):
                load_index(lib, out)

    def test_changed_text_and_model_parameters_invalidate_the_index(self):
        with tempfile.TemporaryDirectory() as temp:
            lib = tiny_library(temp); out = Path(temp) / 'index'
            embedder = HashEmbedder(16)
            manifest = build_index(lib, embedder, out)
            descriptor = embedder.describe(); descriptor['model_id'] = 'different-model'
            with self.assertRaises(IndexInvalid):
                load_index(lib, out, descriptor)
            lib.chunks[manifest['chunk_ids'][0]]['search_sha256'] = 'changed'
            with self.assertRaises(IndexInvalid):
                load_index(lib, out)

    def test_structural_metadata_tampering_invalidates_the_index(self):
        with tempfile.TemporaryDirectory() as temp:
            lib = tiny_library(temp); out = Path(temp) / 'index'
            build_index(lib, HashEmbedder(8), out)
            (out / 'structure.json').write_text('{}', encoding='utf-8')
            with self.assertRaises(IndexInvalid):
                load_index(lib, out)

    def test_numpy_file_is_compatible_and_shape_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'matrix.npy'
            write_npy(path, [1, 0, 0, 1], 2, 2)
            flat, rows, dims = read_npy(path)
            self.assertEqual((list(flat), rows, dims), ([1, 0, 0, 1], 2, 2))
            try:
                import numpy
            except ImportError:
                numpy = None
            if numpy is not None:
                self.assertEqual(numpy.load(path).tolist(), [[1, 0], [0, 1]])
            with self.assertRaises(ValueError):
                write_npy(path, [1], 2, 2)

    def test_cpu_dense_filter_and_topk(self):
        index = DenseIndex([1, 0, 0, 1, -1, 0], ['a', 'b', 'c'], 2, 'cpu', 'float32')
        self.assertEqual(index.search([1, 0], 1)[0][0], 'a')
        self.assertEqual(index.search([1, 0], 2, allowed={'b'}), [('b', 0.0)])
        self.assertEqual(index.search([1, 0], 2, allowed=set()), [])


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag = shared().warm()

    def test_tiers_are_disjoint_and_fusion_uses_ranks(self):
        retriever = Retriever(self.rag)
        self.assertFalse(retriever.tier_sources['core'] & retriever.tier_sources['operational'])
        self.assertFalse(retriever.tier_sources['core'] & retriever.tier_sources['background'])
        result = retriever._fuse('core', [('bm25', 'q', [('A', 'a'), ('B', 'b')]),
                                         ('dense', 'q', [('B', 'b')])])
        self.assertEqual(result[0].unit_id, 'B')
        self.assertEqual(result[0].routes, ['bm25', 'dense'])

    def test_query_vectors_are_reused_across_tiers(self):
        class Encoder(HashEmbedder):
            def __init__(self):
                super().__init__(8); self.calls = []

            def encode(self, texts):
                self.calls.append(texts)
                return super().encode(texts)
        embedder = Encoder()
        dense = unittest.mock.Mock()
        dense.search.return_value = []
        retriever = Retriever(self.rag, dense, embedder)
        queries = [('f', 'сотрудник покинул рабочее место', {'left_workplace'})]
        retriever.rank_tier('core', queries, 'hybrid')
        retriever.rank_tier('operational', queries, 'hybrid')
        self.assertEqual(len(embedder.calls), 1)
        self.assertIn('Термины для поиска:', embedder.calls[0][0])

    def test_dense_source_filter_is_applied_before_topk(self):
        dense = unittest.mock.Mock(); dense.search.return_value = []
        retriever = Retriever(self.rag, dense, HashEmbedder())
        sid = next(iter(retriever.tier_sources['background']))
        retriever.dense_units([0] * 256, 'background', sources={sid})
        allowed = dense.search.call_args.kwargs['allowed']
        self.assertTrue(all(self.rag.source_library().chunks[c]['source_id'] == sid for c in allowed))

    def test_empty_tier_scope_never_expands_to_the_whole_corpus(self):
        retriever = Retriever(self.rag)
        self.assertEqual(retriever.rank_tier('background', [('q', 'касса', ())], 'bm25', sources=set()), [])


class ConfigTests(unittest.TestCase):
    def test_cpu_is_explicit_and_cuda_is_default(self):
        c = load_config()
        self.assertEqual(c.embedder.device, 'cuda:0')
        cpu = c.with_device('cpu')
        self.assertEqual(cpu.embedder.dtype, 'float32')
        self.assertEqual(cpu.generator.device, 'cpu')

    def test_invalid_settings_are_rejected(self):
        c = load_config()
        for bad in (replace(c, retrieval=replace(c.retrieval, top_k=0)),
                    replace(c, retrieval=replace(c.retrieval, tiers=('garbage',))),
                    replace(c, embedder=replace(c.embedder, device='cpu:1')),
                    replace(c, packet=replace(c.packet, budget_tokens=99999)),
                    replace(c, vram_reserve_gib=-1)):
            with self.assertRaises(ValueError):
                bad.validate()


if __name__ == '__main__':
    unittest.main()
