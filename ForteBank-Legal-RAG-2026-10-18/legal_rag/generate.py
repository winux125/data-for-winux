"""Text generation backends for calls A (norm reading) and B (explanation).

One resident model serves both calls. The real backend is Qwen3-VL-4B-Instruct used in
text-only mode through transformers, loaded once per worker; decoding is greedy. The fake
backend replays scripted answers for CPU tests and is labelled `is_real_model=False`
everywhere it appears — it is never evidence that the model works.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
import time


@dataclass
class Generation:
    text: str
    input_tokens: int
    output_tokens: int
    seconds: float
    finish: str                  # eos | length
    backend: str
    is_real_model: bool


class Generator:
    name = 'abstract'
    is_real_model = False

    def chat(self, system, user, max_new_tokens):
        raise NotImplementedError

    def count_tokens(self, text):
        raise NotImplementedError

    def describe(self):
        return dict(name=self.name, is_real_model=self.is_real_model)


class FakeGenerator(Generator):
    """Scripted answers: a list (consumed in order) or a callable(system, user) -> str."""
    name = 'fake_scripted'

    def __init__(self, script):
        self.script, self.calls = script, []

    def chat(self, system, user, max_new_tokens):
        self.calls.append((system, user))
        text = self.script(system, user) if callable(self.script) else self.script.pop(0)
        return Generation(text, len(user) // 3, len(text) // 3, 0.0, 'eos', self.name, False)

    def count_tokens(self, text):
        return len(text) // 3 + 1


class QwenTextGenerator(Generator):
    """Qwen3-VL-4B-Instruct, text-only chat, greedy decoding, CUDA by default."""
    is_real_model = True

    def __init__(self, config):
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        if config.device.startswith('cuda') and not torch.cuda.is_available():
            raise RuntimeError(f'Configured {config.device} but CUDA is unavailable; select cpu explicitly')
        self.torch, self.config = torch, config
        started = time.perf_counter()
        self.processor = AutoProcessor.from_pretrained(config.model_id, revision=config.revision,
                                                       local_files_only=config.local_files_only)
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            config.model_id, revision=config.revision, dtype=getattr(torch, config.dtype),
            local_files_only=config.local_files_only, attn_implementation='sdpa').to(config.device).eval()
        if config.device.startswith('cuda'):
            torch.cuda.synchronize()
        self.load_seconds = time.perf_counter() - started
        self.name = f'{config.model_id}@{config.revision}'

    def count_tokens(self, text):
        return len(self.processor.tokenizer(text, add_special_tokens=False)['input_ids'])

    def chat(self, system, user, max_new_tokens):
        torch = self.torch
        messages = [{'role': 'system', 'content': [{'type': 'text', 'text': system}]},
                    {'role': 'user', 'content': [{'type': 'text', 'text': user}]}]
        inputs = self.processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                                    return_dict=True, return_tensors='pt')
        inputs.pop('token_type_ids', None)
        input_tokens = int(inputs['input_ids'].shape[1])
        if input_tokens > self.config.max_input_tokens:
            raise ValueError(f'Prompt has {input_tokens} tokens > configured {self.config.max_input_tokens}')
        inputs = {k: v.to(self.config.device) for k, v in inputs.items()}
        if self.config.device.startswith('cuda'):
            torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False, use_cache=True)
        if self.config.device.startswith('cuda'):
            torch.cuda.synchronize()
        seconds = time.perf_counter() - started
        generated = output[:, input_tokens:]
        text = self.processor.batch_decode(generated, skip_special_tokens=True,
                                           clean_up_tokenization_spaces=False)[0]
        count = int(generated.shape[1])
        return Generation(text, input_tokens, count, seconds, 'length' if count >= max_new_tokens else 'eos',
                          self.name, True)

    def describe(self):
        info = dict(name=self.name, is_real_model=True, device=self.config.device, dtype=self.config.dtype,
                    load_seconds=round(self.load_seconds, 2))
        if self.config.device.startswith('cuda'):
            info['peak_vram_allocated_gib'] = round(self.torch.cuda.max_memory_allocated() / 2**30, 3)
        return info


def parse_json_object(text):
    """First complete JSON object in a model answer (code fences tolerated); ValueError otherwise."""
    cleaned = re.sub(r'^```(?:json)?\s*|\s*```\s*$', '', text.strip())
    start = cleaned.find('{')
    if start < 0:
        raise ValueError('No JSON object in the answer')
    depth, in_string, escape = 0, False, False
    for i, ch in enumerate(cleaned[start:], start):
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start:i + 1])
    raise ValueError('Truncated JSON object in the answer')


def make_generator(config):
    return QwenTextGenerator(config)


def generation_record(g):
    return {k: v for k, v in asdict(g).items() if k != 'text'}
