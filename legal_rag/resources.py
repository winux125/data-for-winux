"""Runtime device diagnostics; no external provider calls or implicit CPU fallback."""
from __future__ import annotations

import importlib.metadata
import platform
import sys


def environment():
    versions = {}
    for package in ('torch', 'transformers', 'numpy', 'tokenizers', 'huggingface-hub'):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    result = dict(python=sys.version.split()[0], platform=platform.platform(), packages=versions,
                  cuda_available=False, devices=[])
    if versions['torch']:
        import torch
        result['cuda_available'] = torch.cuda.is_available()
        result['cuda_version'] = torch.version.cuda
        if result['cuda_available']:
            for i in range(torch.cuda.device_count()):
                free, total = torch.cuda.mem_get_info(i)
                result['devices'].append(dict(device=f'cuda:{i}', name=torch.cuda.get_device_name(i),
                                               free_gib=round(free / 2**30, 3), total_gib=round(total / 2**30, 3)))
    return result


def cuda_preflight(config):
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError('CUDA mode requires PyTorch; this interpreter has no torch installed') from exc
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA was requested but is unavailable; select CPU explicitly for control runs')
    devices = {m.device for m in (config.embedder, config.generator, config.reranker)
               if m is not None and m.enabled and m.device.startswith('cuda')}
    result = {}
    for device in devices:
        free, total = torch.cuda.mem_get_info(device)
        if free / 2**30 <= config.vram_reserve_gib:
            raise RuntimeError(f'{device}: free VRAM is below the configured reserve')
        if any(m and m.device == device and m.dtype == 'bfloat16'
               for m in (config.embedder, config.generator, config.reranker)):
            with torch.cuda.device(device):
                if not torch.cuda.is_bf16_supported():
                    raise RuntimeError(f'{device}: configured bfloat16 is unsupported')
        result[device] = dict(free_gib=free / 2**30, total_gib=total / 2**30,
                              allocated_gib=torch.cuda.memory_allocated(device) / 2**30,
                              reserved_gib=torch.cuda.memory_reserved(device) / 2**30)
    return result


def memory_snapshot():
    """Process RAM and CUDA allocator state. Peaks are process-wide, not per-request deltas."""
    result = dict(peak_scope='process_lifetime', ram_rss_bytes=None, cuda={})
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (key, ctypes.c_size_t) for key in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                                                 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                                                 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
        data = Counters(); data.cb = ctypes.sizeof(data)
        process = ctypes.windll.kernel32.GetCurrentProcess
        process.restype = wintypes.HANDLE
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
        if query(process(), ctypes.byref(data), data.cb):
            result.update(ram_rss_bytes=data.WorkingSetSize, ram_peak_rss_bytes=data.PeakWorkingSetSize)
    else:
        import resource
        result['ram_peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
    try:
        import torch
    except ImportError:
        return result
    if torch.cuda.is_available():
        for device in range(torch.cuda.device_count()):
            torch.cuda.synchronize(device)
            free, total = torch.cuda.mem_get_info(device)
            result['cuda'][f'cuda:{device}'] = dict(free_bytes=free, total_bytes=total,
                allocated_bytes=torch.cuda.memory_allocated(device), reserved_bytes=torch.cuda.memory_reserved(device),
                peak_allocated_bytes=torch.cuda.max_memory_allocated(device),
                peak_reserved_bytes=torch.cuda.max_memory_reserved(device))
    return result
