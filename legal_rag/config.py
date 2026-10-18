"""Runtime configuration of the neural components (embedder, reranker, generator).

`cuda:0` is the default device. A CPU backend must be selected explicitly (tests, control
runs); a missing GPU never silently falls back. Model revisions are pinned; weights are
loaded only from the local cache unless `local_files_only` is explicitly disabled for a
one-time download from the official repository.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
import re
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent / 'data' / 'runtime_config.json'
DEVICES = ('cuda', 'cpu')
DTYPES = ('float32', 'float16', 'bfloat16')


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    revision: str | None
    device: str = 'cuda:0'
    dtype: str = 'float16'
    batch_size: int = 16
    max_input_tokens: int = 512
    max_new_tokens: int = 0
    local_files_only: bool = True
    enabled: bool = True

    def validate(self, name):
        if not re.fullmatch(r'cpu|cuda(?::\d+)?', self.device):
            raise ValueError(f'{name}: device must be cuda[:N] or cpu')
        if self.dtype not in DTYPES:
            raise ValueError(f'{name}: dtype must be one of {DTYPES}')
        if self.batch_size < 1 or self.max_input_tokens < 16 or self.max_new_tokens < 0:
            raise ValueError(f'{name}: invalid batch or length limits')
        if self.device == 'cpu' and self.dtype == 'float16':
            raise ValueError(f'{name}: float16 on CPU is not supported; use float32 or bfloat16')
        if not self.model_id or (self.revision is not None and not isinstance(self.revision, str)):
            raise ValueError(f'{name}: invalid model ID or revision')


@dataclass(frozen=True)
class RetrievalConfig:
    mode: str = 'hybrid'              # bm25 | dense | hybrid
    rrf_k: int = 60
    candidates_per_retriever: int = 50
    top_k: int = 5
    tiers: tuple = ('core', 'operational')
    use_lexicon: bool = True


@dataclass(frozen=True)
class PacketConfig:
    budget_tokens: int = 3000
    answer_reserve_tokens: int = 700


@dataclass(frozen=True)
class PublicationConfig:
    # An explicit deployment policy, never a fabricated human review record.
    mode: str = 'reviewed_only'
    rule_ids: tuple = ()
    allow_grounded_fallback: bool = False


@dataclass(frozen=True)
class ExecutionConfig:
    explain_supported_only: bool = False
    max_general_candidates: int | None = None
    max_model_calls: int | None = None


@dataclass(frozen=True)
class RuntimeConfig:
    embedder: ModelConfig
    generator: ModelConfig
    reranker: ModelConfig | None = None
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    packet: PacketConfig = field(default_factory=PacketConfig)
    vram_reserve_gib: float = 1.5
    publication: PublicationConfig = field(default_factory=PublicationConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    def validate(self):
        if self.publication.mode not in ('reviewed_only', 'evidence_assisted'):
            raise ValueError('Unknown publication policy')
        if not isinstance(self.publication.allow_grounded_fallback, bool):
            raise ValueError('allow_grounded_fallback must be a boolean')
        if not isinstance(self.execution.explain_supported_only, bool):
            raise ValueError('explain_supported_only must be a boolean')
        for value in (self.execution.max_general_candidates, self.execution.max_model_calls):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('Execution limits must be non-negative integers or null')
        if any(not isinstance(v, str) for v in self.publication.rule_ids):
            raise ValueError('publication.rule_ids must contain rule IDs')
        self.embedder.validate('embedder')
        self.generator.validate('generator')
        if self.reranker is not None:
            self.reranker.validate('reranker')
        if self.retrieval.mode not in ('bm25', 'dense', 'hybrid'):
            raise ValueError('retrieval.mode must be bm25, dense or hybrid')
        if self.generator.max_new_tokens < 64:
            raise ValueError('generator.max_new_tokens must leave room for the structured answer')
        if not self.generator.enabled:
            raise ValueError('generator.enabled=false is unsupported; use explicit template-only mode')
        if self.retrieval.mode != 'bm25' and not self.embedder.enabled:
            raise ValueError('dense/hybrid requires the embedder to be enabled')
        if not 1 <= self.retrieval.top_k <= 50 or not 1 <= self.retrieval.candidates_per_retriever <= 50:
            raise ValueError('retrieval top_k and candidates_per_retriever must be in 1..50')
        if self.retrieval.rrf_k < 1 or set(self.retrieval.tiers) - {'core', 'operational', 'background'}:
            raise ValueError('invalid RRF constant or retrieval tiers')
        if len(self.retrieval.tiers) != len(set(self.retrieval.tiers)) or not self.retrieval.tiers:
            raise ValueError('retrieval tiers must be nonempty and unique')
        if self.packet.budget_tokens < 64 or self.packet.answer_reserve_tokens < 64:
            raise ValueError('packet and explanation budgets must be at least 64 tokens')
        if self.packet.budget_tokens >= self.generator.max_input_tokens:
            raise ValueError('packet budget must leave input room for instructions and observations')
        if not math.isfinite(self.vram_reserve_gib) or self.vram_reserve_gib < 0:
            raise ValueError('VRAM reserve must be finite and non-negative')
        return self

    def to_dict(self):
        return asdict(self)

    def with_device(self, device, dtype=None):
        """Explicit override (e.g. --device cpu for a control run)."""
        def swap(model):
            if model is None:
                return None
            data = asdict(model)
            data['device'] = device
            if dtype:
                data['dtype'] = dtype
            elif device == 'cpu' and data['dtype'] == 'float16':
                data['dtype'] = 'float32'
            return ModelConfig(**data)
        return RuntimeConfig(swap(self.embedder), swap(self.generator), swap(self.reranker), self.retrieval,
                             self.packet, self.vram_reserve_gib, self.publication, self.execution).validate()


def load_config(path=DEFAULT_CONFIG):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    reranker = data.get('reranker')
    return RuntimeConfig(
        embedder=ModelConfig(**data['embedder']), generator=ModelConfig(**data['generator']),
        reranker=ModelConfig(**reranker) if reranker else None,
        retrieval=RetrievalConfig(**{**data.get('retrieval', {}),
                                     'tiers': tuple(data.get('retrieval', {}).get('tiers', ('core', 'operational')))}),
        packet=PacketConfig(**data.get('packet', {})), vram_reserve_gib=data.get('vram_reserve_gib', 1.5),
        publication=PublicationConfig(**{**data.get('publication', {}),
            'rule_ids': tuple(data.get('publication', {}).get('rule_ids', ())) }),
        execution=ExecutionConfig(**data.get('execution', {}))).validate()
