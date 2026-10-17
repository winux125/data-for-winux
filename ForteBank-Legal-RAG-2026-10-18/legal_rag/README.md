# Legal RAG: integration and validation

This package accepts structured observations. It does not read videos, run JEPA,
extract frames, or turn classifier scores into legal facts.

```text
Video -> external Forte JEPA (label + at most one approximate timestamp)
      -> external frame extraction -> visual Qwen -> ObservationBundle
      -> Legal RAG: tiered BM25 / BGE-M3 / hybrid RRF
      -> complete parent norm + dependencies -> application -> explanation
```

The final JEPA release is `JEPA-FULL.zip` in the project root; its inspected README
is copied to `research/jepa_full_audit_2026-10-18/README.md`. It supersedes the older
README from Downloads: FULL has a CPU code path and was refitted on all 40 videos.
CPU inference and independent quality of FULL remain unverified; the previous
28/12 model's F1 must not be attributed to FULL.
It emits no violation type and no selected frames. No timestamp is invented when
the release reports `uncertain`. Its label/score belongs to the orchestrator;
`parse_input()` rejects it anywhere inside RAG input, including provenance.

## One integration entry point

```python
from legal_rag import shared
from legal_rag.config import load_config

rag = shared()
worker = rag.runtime(load_config()).warm()  # one resident BGE + Qwen per worker
result = worker.analyze(observation_json).to_dict()
```

Calls on one worker are serialized. The JSON contract is in `contracts.py`.
`examples/leaving_workplace.json` is an explicitly **synthetic** input, not an
annotated video. Every decided fact needs evidence references. Missing facts,
inferred roles, unobserved actions, ambiguous scopes and conflicting observations
remain unknown. Refuted means an observed absence; it is never changed to confirmed.

The legal decision is per norm/event: `violation_supported`, `refuted`,
`exception_applies`, `insufficient`, `not_applicable_scope`. An empty candidate set
or all validated irrelevant candidates produce `no_norm` with `exhaustive=false`;
this does not certify compliance with all law.

## Current implementation

- Structural parents/children over 54 verified source snapshots. Source text and
  hashes are retained. Article parts are distinguished from other articles;
  repeated numbering is separated by containers. Fallback spans retain document
  citations. Hierarchical node IDs, source metadata, unit/child hashes and links
  are exported into the embedding index's `structure.json`.
- Retrieval tiers stay separate: the five core acts, other operational sources,
  and background sources reached through explicit document links. RRF uses ranks
  within a tier. BM25 score and cosine are not legal confidence.
- Predicates and multiword contextual phrases drive the lexicon. Both sparse and
  dense queries can use the lexicon; it changes retrieval only. Query encoding is
  reused across tiers for a request.
- `source_packet.py` restores the exact whole parent. It adds explicit reference
  closure for the core acts, definitions, and bounded exception context. Omitted
  dependencies, suspended wording, fallback structure and unresolved applicable
  clauses leave completeness false. This is bounded dependency coverage, not proof
  that every potentially relevant norm has been found.
- A rule card maps predicates/polarity to condition states in code. Missing mappings
  stay unknown. Draft cards remain drafts. Other norms use Qwen call A for a structured
  reading with exact quotes. Code validates the reading and computes the decision.
- The same text-mode `Qwen/Qwen3-VL-4B-Instruct` serves call B. It explains the fixed
  decision; citations, actual evidence IDs and times are inserted by code. Invalid
  answers get one retry, then an explicitly labelled template fallback.
- Checks cover JSON shape, quote offsets, exception-segment accounting, polarity
  cues, unknowns and reference allowlists. **They do not establish semantic entailment.**
  A fluent wrong paraphrase with valid IDs can still require human review.

`NormAssessment` includes full source quotes, supporting norms, condition mappings,
scope, decision reasons, generator identity, attempts/errors, evidence and publication
status. Draft cards cannot publish. General model-read norms are analysis-only pending
review. Fake/template backends cannot publish. No reviewer record is fabricated.
Document-level citations are supported; an exact clause is not mandatory for a
fallback source, but such a fallback is not silently treated as complete.

## CPU checks, without weights or network

From the project root, using Python 3.11+:

```powershell
python -B -m unittest discover -s legal_rag/tests -t .
python -B -m legal_rag doctor --device cpu
python -B -m legal_rag analyze --input legal_rag/examples/leaving_workplace.json --device cpu --retrieval bm25 --top-k 1 --template-only --output tmp/rag_answer.json
python -B -m legal_rag bench --device cpu --retrieval bm25 --output research/rag_cpu_bench.json
```

Template-only mode is a wiring/decision check. It is not a successful Qwen run.
CPU tests replay scripted model replies for call A/B and test failure handling;
their pass rate is not a language-model quality metric.

## Real models on an existing CUDA server

Use a separate virtual environment. These commands prepare the RAG environment;
they do not modify or reinstall the JEPA release. No instance is rented here.

```bash
python3.11 -m venv .venv-rag
source .venv-rag/bin/activate
python -m pip install torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r legal_rag/requirements-gpu.txt
```

The runtime config pins model revisions and defaults to `local_files_only=true`.
If the weights are absent, download these public repositories once (only public
weights are requested; no video or observations are sent):

```bash
hf download BAAI/bge-m3 --revision 5617a9f61b028005a4858fdac845db406aefb181
hf download Qwen/Qwen3-VL-4B-Instruct --revision ebb281ec70b05090aa6165b016eac8ec08e71b17
python -B -m legal_rag doctor
python -B -m legal_rag embed --output data/legal_index/bge-m3
python -B -m legal_rag analyze --input legal_rag/examples/leaving_workplace.json --index-dir data/legal_index/bge-m3 --output tmp/rag_qwen_answer.json
python -B -m legal_rag bench --run-models --index-dir data/legal_index/bge-m3 --output research/rag_gpu_bench.json
```

Model API syntax was checked against Transformers 4.57.3 Qwen3-VL documentation
and the official FlagEmbedding BGE-M3 documentation. This is **not runtime validation**
of these pinned weights. Confirm the repositories/revisions and their licences before
deployment; unavailable pinned weights fail rather than falling back to a newer revision.

`embed` writes `vectors.npy`, `structure.json` and `manifest.json`. The manifest pins
row order, source metadata hash, structural metadata hash, model/revision, CLS pooling,
L2 normalization, length/truncation, compute/storage dtype and parser/template versions.
Changed metadata/text/model parameters invalidate the index. Batch reduction on CUDA
OOM and truncated-text counts are recorded. Hash embeddings are only for tests and
require an explicit separate output directory (`embed --test-embedder --output ...`).

CPU handles parsing, BM25, RRF, metadata, packet assembly and validation. CUDA handles
BGE encoding, dense matmul/top-k and Qwen A/B. No silent CUDA-to-CPU fallback occurs.
The worker records initial free VRAM and allocated/reserved peaks. A reserve check
is not proof that all models fit; measure simultaneous residency with JEPA on the
actual host. CPU/GPU agreement and fp16/fp32 quality remain separate experiments.

## What the benchmark measures

`bench` compares tiered core BM25 with/without the lexicon on the existing 36 positive
development queries plus three irrelevant controls. It reports exact-parent and document
recall separately and preserves per-query ranks. `--run-models` additionally compares
dense/hybrid and runs synthetic end-to-end smoke inputs. Its four target cases are a
supported breach, a refutation, missing information and an applicable exception.

The queries were written from the original five acts and have been used for tuning.
They do not validate coverage of the other 49 sources. The synthetic smoke cases
are not blind ground truth. No independent frozen test or human semantic scores
are invented. Before selecting hybrid as the default, independently annotate new
paraphrases/exact terms/negation pairs and confirm improvement; the config's hybrid
default is the architecture candidate, not a measured winning recipe.

The optional reranker and the full approximately 70-case human-labelled application/
generation benchmark are still pending. Enabling an unimplemented reranker fails
explicitly. See `research/LEGAL_RAG_FINAL_STATUS.md` for the actual run status.
