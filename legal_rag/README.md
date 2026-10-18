# Legal RAG

The canonical package is `legal_rag/` in the service repository. It receives structured visual observations, not images, video or JEPA scores. It provides tiered BM25/BGE-M3 hybrid retrieval, full parent norms and related provisions, application and Qwen-generated explanations with validated source bindings.

Source snapshots, metadata, rule cards, lexicon and evaluation queries are included. Weights, generated indices and private results are excluded. The runtime does not require the original RAG ZIP or an overlay build.

From the repository root:

```bash
python scripts/verify_runtime.py
python -m unittest discover -s legal_rag/tests -t .
python -m legal_rag search "кассир покинул рабочее место"
```

Production uses `config/rag-mvp.json`, visual Qwen uses `config/observer.json`; `config/rag-cpu-smoke.json` is an explicit CPU control. Use the root requirements.txt for the integrated service. Loading neural models additionally requires the pinned weights and sufficient memory.

The active detector is JEPA-LGBM-FULL. JEPA selects candidates, external Qwen8B provides observations, this package retrieves norms and Qwen4B produces grounded explanations. `possible_indications` is a distinct human-review contract; it does not sign draft cards or turn unknown legal conditions into facts.

See [architecture](../docs/LEGAL_RAG_QWEN_README.md), [deployment](../docs/DEPLOYMENT.md) and [service README](../README.md).
