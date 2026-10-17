"""Dense top-k over normalized vectors: torch matmul on the configured device, or a pure-Python control."""
from __future__ import annotations

import heapq
import time


class DenseIndex:
    def __init__(self, flat, chunk_ids, dims, device='cpu', dtype='float32'):
        self.chunk_ids, self.dims, self.device = list(chunk_ids), dims, device
        self.position = {c: i for i, c in enumerate(self.chunk_ids)}
        self.backend = 'python'
        self.upload_seconds = 0.0
        try:
            import torch
        except ImportError:
            torch = None
        if device.startswith('cuda') and (torch is None or not torch.cuda.is_available()):
            raise RuntimeError(f'Dense index configured on {device} but CUDA is unavailable')
        if torch is not None:
            started = time.perf_counter()
            matrix = torch.tensor(flat, dtype=torch.float32).reshape(len(self.chunk_ids), dims)
            self.matrix = matrix.to(device=device, dtype=getattr(torch, dtype))
            if device.startswith('cuda'):
                torch.cuda.synchronize()
            self.upload_seconds = time.perf_counter() - started
            self.torch, self.backend = torch, 'torch'
        else:
            self.flat = flat

    def search(self, vector, k=50, allowed=None):
        """[(chunk_id, cosine)] best first; `allowed` restricts rows (e.g. one tier's sources)."""
        if self.backend == 'torch':
            torch = self.torch
            query = torch.tensor(vector, dtype=self.matrix.dtype, device=self.matrix.device)
            scores = self.matrix @ query
            if allowed is not None:
                mask = torch.full_like(scores, float('-inf'))
                rows = [self.position[c] for c in allowed if c in self.position]
                if not rows:
                    return []
                index = torch.tensor(rows, device=scores.device)
                mask[index] = scores[index]
                scores = mask
            top = torch.topk(scores.float(), min(k, scores.shape[0]))
            if self.matrix.device.type == 'cuda':
                torch.cuda.synchronize()
            return [(self.chunk_ids[i], float(s)) for s, i in zip(top.values.tolist(), top.indices.tolist())
                    if s != float('-inf')]
        rows = range(len(self.chunk_ids)) if allowed is None else [self.position[c] for c in allowed
                                                                  if c in self.position]
        dims, flat = self.dims, self.flat
        scored = ((sum(flat[r * dims + j] * vector[j] for j in range(dims)), r) for r in rows)
        return [(self.chunk_ids[r], s) for s, r in heapq.nlargest(k, scored)]
