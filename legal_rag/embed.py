"""Dense embeddings of child chunks (BGE-M3) and a versioned on-disk index.

Vectors are written as a float32 .npy (format 1.0, written without numpy) next to a
manifest that pins the row order of chunk IDs, the hash of every embedded text, the
model and revision, pooling, normalization, truncation and the parser/template version.
Loading checks all of it against the current library and the configured model; any
mismatch invalidates the index instead of silently mixing vectors.
"""
from __future__ import annotations

import array
import ast
import hashlib
import json
import math
from pathlib import Path
from dataclasses import asdict
import struct
import sys
import time

from .text import stem_tokens
from .units import PARSER_VERSION
from .paths import RESOURCES, ROOT

INDEX_SCHEMA = 'legal_rag.embedding_index.v2'
TEXT_TEMPLATE = PARSER_VERSION + ':search_text'  # headings[-2:] + lead + child normative lines
DEFAULT_INDEX_DIR = (Path.cwd() if RESOURCES.is_dir() else ROOT) / 'data' / 'legal_index' / 'bge-m3'
INDEX_ROLES = ('operational', 'background')


class IndexInvalid(ValueError):
    pass


# .npy without numpy ------------------------------------------------------------

def write_npy(path, flat, rows, dims):
    if len(flat) != rows * dims:
        raise ValueError('Vector buffer size does not match rows x dims')
    header = "{'descr': '<f4', 'fortran_order': False, 'shape': (%d, %d), }" % (rows, dims)
    header += ' ' * (63 - (10 + len(header)) % 64) + '\n'
    data = array.array('f', flat)
    if sys.byteorder != 'little':
        data.byteswap()
    with Path(path).open('wb') as handle:
        handle.write(b'\x93NUMPY\x01\x00' + struct.pack('<H', len(header)) + header.encode('latin1'))
        handle.write(data.tobytes())


def read_npy(path):
    raw = Path(path).read_bytes()
    if raw[:6] != b'\x93NUMPY' or raw[6] != 1:
        raise IndexInvalid('Unsupported .npy file')
    length = struct.unpack('<H', raw[8:10])[0]
    header = ast.literal_eval(raw[10:10 + length].decode('latin1'))
    if header['descr'] != '<f4' or header['fortran_order']:
        raise IndexInvalid('Expected little-endian float32 C-order vectors')
    rows, dims = header['shape']
    data = array.array('f')
    data.frombytes(raw[10 + length:])
    if sys.byteorder != 'little':
        data.byteswap()
    if len(data) != rows * dims:
        raise IndexInvalid('Truncated vector file')
    return data, rows, dims


# Embedders --------------------------------------------------------------------

class Embedder:
    name = 'abstract'
    is_real_model = False

    def encode(self, texts):
        """List of L2-normalized float vectors."""
        raise NotImplementedError

    def describe(self):
        raise NotImplementedError


class HashEmbedder(Embedder):
    """Deterministic stem-hashing vectors for CPU wiring tests only — not a semantic model."""
    name = 'hash_test_embedder'

    def __init__(self, dims=256):
        self.dims = dims

    def encode(self, texts):
        result = []
        for text in texts:
            vector = [0.0] * self.dims
            for stem in stem_tokens(text):
                digest = hashlib.sha256(stem.encode('utf-8')).digest()
                vector[int.from_bytes(digest[:4], 'little') % self.dims] += 1.0 if digest[4] % 2 else -1.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            result.append([v / norm for v in vector])
        return result

    def describe(self):
        return dict(model_id=self.name, revision=None, pooling='hashed_stems', normalization='l2',
                    max_length=None, truncation=None, dims=self.dims, compute_dtype='float32', device='cpu',
                    is_real_model=False)


class BgeM3Embedder(Embedder):
    """BAAI/bge-m3 dense vectors: CLS pooling + L2 normalization (the model's dense retrieval head)."""
    is_real_model = True

    def __init__(self, config):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.torch, self.config = torch, config
        if config.device.startswith('cuda') and not torch.cuda.is_available():
            raise RuntimeError(f'Configured {config.device} but CUDA is unavailable; select cpu explicitly')
        dtype = getattr(torch, config.dtype)
        started = time.perf_counter()
        self.tokenizer = AutoTokenizer.from_pretrained(config.model_id, revision=config.revision,
                                                       local_files_only=config.local_files_only)
        self.model = AutoModel.from_pretrained(config.model_id, revision=config.revision, dtype=dtype,
                                               local_files_only=config.local_files_only).to(config.device).eval()
        self.load_seconds = time.perf_counter() - started
        self.batch_size = config.batch_size
        self.batch_reductions = []
        self.truncated_texts = 0
        self.encoded_texts = 0
        self.name = config.model_id
        self.dims = self.model.config.hidden_size

    def _encode_batch(self, texts):
        torch = self.torch
        lengths = self.tokenizer(texts, truncation=False, return_length=True)['length']
        truncated = sum(n > self.config.max_input_tokens for n in lengths)
        inputs = self.tokenizer(texts, padding=True, truncation=True, max_length=self.config.max_input_tokens,
                                return_tensors='pt').to(self.config.device)
        with torch.inference_mode():
            hidden = self.model(**inputs).last_hidden_state[:, 0]
            hidden = torch.nn.functional.normalize(hidden.float(), dim=-1)
        self.truncated_texts += truncated
        self.encoded_texts += len(texts)
        return hidden.cpu().tolist()

    def encode(self, texts):
        torch, result, start = self.torch, [], 0
        while start < len(texts):
            batch = texts[start:start + self.batch_size]
            try:
                result.extend(self._encode_batch(batch))
                start += len(batch)
            except torch.cuda.OutOfMemoryError:
                if self.batch_size == 1:
                    raise
                torch.cuda.empty_cache()
                self.batch_size = max(1, self.batch_size // 2)   # controlled reduction, recorded in the manifest
                self.batch_reductions.append(self.batch_size)
        return result

    def describe(self):
        return dict(model_id=self.config.model_id, revision=self.config.revision, pooling='cls',
                    normalization='l2', max_length=self.config.max_input_tokens, truncation='right',
                    dims=self.dims, compute_dtype=self.config.dtype, device=self.config.device, is_real_model=True,
                    batch_size_final=self.batch_size, batch_reductions=self.batch_reductions,
                    encoded_texts=self.encoded_texts, truncated_texts=self.truncated_texts)


def make_embedder(config):
    if config.model_id == HashEmbedder.name:
        return HashEmbedder()
    return BgeM3Embedder(config)


# Index build / load -------------------------------------------------------------

def _rows(library, roles=INDEX_ROLES):
    rows = []
    for chunk_id, chunk in library.chunks.items():
        source = library.sources[chunk['source_id']]
        unit = library.units[chunk['unit_id']]
        if source['role'] in roles and unit.indexed and unit.status != 'repealed' and source.get('official_in_force'):
            rows.append((chunk_id, chunk['search_text'], chunk['search_sha256']))
    return rows


def _sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_index(library, embedder, out_dir=DEFAULT_INDEX_DIR, roles=INDEX_ROLES, progress=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = _rows(library, roles)
    started = time.perf_counter()
    flat, step = [], 256
    for start in range(0, len(rows), step):
        for vector in embedder.encode([text for _, text, _ in rows[start:start + step]]):
            flat.extend(vector)
        if progress:
            progress(min(start + step, len(rows)), len(rows))
    seconds = time.perf_counter() - started
    info = embedder.describe()
    write_npy(out_dir / 'vectors.npy', flat, len(rows), info['dims'])
    manifest = dict(schema=INDEX_SCHEMA, embedder=info, parser_version=PARSER_VERSION, text_template=TEXT_TEMPLATE,
                    library_id=library.manifest['library_id'], library_manifest_sha256=_sha_file(library.path),
                    roles=list(roles), rows=len(rows), dims=info['dims'], stored_dtype='float32',
                    vectors_sha256=_sha_file(out_dir / 'vectors.npy'), indexing_seconds=round(seconds, 2),
                    chunk_ids=[c for c, _, _ in rows], text_sha256=[h for _, _, h in rows])
    metadata = dict(parser_version=PARSER_VERSION, sources=library.sources, hierarchy_nodes=library.structure_nodes,
                    units={u: asdict(unit) for u, unit in library.units.items()},
                    chunks={cid: {k: v for k, v in library.chunks[cid].items() if k not in ('text', 'search_text')}
                            for cid, _, _ in rows})
    metadata_path = out_dir / 'structure.json'
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=1), encoding='utf-8')
    manifest['structure_sha256'] = _sha_file(metadata_path)
    manifest['truncated_texts'] = getattr(embedder, 'truncated_texts', 0)
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    return manifest


def load_index(library, out_dir=DEFAULT_INDEX_DIR, expect=None):
    """Return (flat_vectors, chunk_ids, manifest); raise IndexInvalid on any mismatch."""
    out_dir = Path(out_dir)
    manifest_path = out_dir / 'manifest.json'
    if not manifest_path.exists():
        raise IndexInvalid(f'No embedding index at {out_dir}; build it with `python -m legal_rag embed`')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema') != INDEX_SCHEMA or manifest['parser_version'] != PARSER_VERSION \
            or manifest['text_template'] != TEXT_TEMPLATE:
        raise IndexInvalid('Index schema, parser or text template changed')
    if _sha_file(out_dir / 'vectors.npy') != manifest['vectors_sha256']:
        raise IndexInvalid('Vector file hash differs from manifest')
    if _sha_file(library.path) != manifest['library_manifest_sha256']:
        raise IndexInvalid('Source library metadata changed since indexing')
    if _sha_file(out_dir / 'structure.json') != manifest.get('structure_sha256'):
        raise IndexInvalid('Structural metadata changed since indexing')
    if len(set(manifest['chunk_ids'])) != manifest['rows'] or len(manifest['text_sha256']) != manifest['rows']:
        raise IndexInvalid('Duplicate rows or invalid text hash mapping')
    current = {c: h for c, _, h in _rows(library, tuple(manifest['roles']))}
    indexed = dict(zip(manifest['chunk_ids'], manifest['text_sha256']))
    if current != indexed:
        changed = sum(1 for c in set(current) | set(indexed) if current.get(c) != indexed.get(c))
        raise IndexInvalid(f'{changed} chunk texts or IDs changed since indexing; rebuild the index')
    if expect is not None:
        for key in ('model_id', 'revision', 'pooling', 'normalization', 'max_length'):
            if manifest['embedder'].get(key) != expect.get(key):
                raise IndexInvalid(f'Index {key}={manifest["embedder"].get(key)!r} != configured {expect.get(key)!r}')
    flat, rows, dims = read_npy(out_dir / 'vectors.npy')
    if rows != manifest['rows'] or dims != manifest['dims']:
        raise IndexInvalid('Vector shape differs from manifest')
    return flat, manifest['chunk_ids'], manifest


def expected_descriptor(config):
    """What a loaded index must match for the configured embedder (checked before loading weights)."""
    if config.model_id == HashEmbedder.name:
        return HashEmbedder().describe()
    return dict(model_id=config.model_id, revision=config.revision, pooling='cls', normalization='l2',
                max_length=config.max_input_tokens)
