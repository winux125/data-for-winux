"""Constrained local text generation; fake generators retain their test interface."""
import time
import logging

from .generate import Generation


def parser_config():
    from lmformatenforcer import CharacterLevelParserConfig
    config = CharacterLevelParserConfig()
    config.alphabet += ''.join(chr(i) for i in range(0x0400, 0x0500)) + '«»„“”—–\u00a0'
    return config


def eos_kwargs(generator):
    """The grammar recognizes the tokenizer EOS, not extra model stop tokens.

    Qwen's generation config also lists endoftext/pad. Suppress that alternative
    so it cannot terminate inside a JSON string before the grammar permits EOS.
    """
    eos = generator.processor.tokenizer.eos_token_id
    if eos is None:
        raise ValueError('Structured decoding requires a tokenizer EOS')
    model_eos = generator.model.generation_config.eos_token_id
    model_eos = model_eos if isinstance(model_eos, (list, tuple)) else [model_eos]
    suppressed = set(generator.model.generation_config.suppress_tokens or [])
    suppressed.update(token for token in model_eos if token is not None and token != eos)
    return {'eos_token_id': eos, 'suppress_tokens': sorted(suppressed)}


def chat(generator, system, user, max_tokens, schema):
    if not all(hasattr(generator, name) for name in ('processor', 'model', 'torch', 'config')):
        return generator.chat(system, user, max_tokens)
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn, build_token_enforcer_tokenizer_data
    torch, config = generator.torch, generator.config
    messages = [{'role': 'system', 'content': [{'type': 'text', 'text': system}]},
                {'role': 'user', 'content': [{'type': 'text', 'text': user}]}]
    inputs = generator.processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
        return_dict=True, return_tensors='pt')
    inputs.pop('token_type_ids', None)
    count = int(inputs['input_ids'].shape[1])
    if count > config.max_input_tokens:
        raise ValueError('Structured prompt exceeds configured input budget')
    inputs = {k: v.to(config.device) for k, v in inputs.items()}
    logging.info('Structured parser start input_tokens=%s', count)
    parser_started = time.perf_counter()
    if not hasattr(generator, '_format_tokenizer_data'):
        generator._format_tokenizer_data = build_token_enforcer_tokenizer_data(generator.processor.tokenizer)
    prefix = build_transformers_prefix_allowed_tokens_fn(generator._format_tokenizer_data,
        JsonSchemaParser(schema, config=parser_config()))
    logging.info('Structured parser ready seconds=%.3f', time.perf_counter() - parser_started)
    if config.device.startswith('cuda'):
        torch.cuda.synchronize()
    started = time.perf_counter()
    with torch.inference_mode():
        output = generator.model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False,
            use_cache=True, prefix_allowed_tokens_fn=prefix, **eos_kwargs(generator))
    if config.device.startswith('cuda'):
        torch.cuda.synchronize()
    text = generator.processor.batch_decode(output[:, count:], skip_special_tokens=True,
        clean_up_tokenization_spaces=False)[0]
    length = int(output.shape[1] - count)
    logging.info('Structured output_tokens=%s seconds=%.3f', length, time.perf_counter() - started)
    return Generation(text, count, length, time.perf_counter() - started,
                      'length' if length >= max_tokens else 'eos', generator.name, True)


def explanation_schema(node_id):
    return {'type': 'object', 'additionalProperties': False,
        'properties': {'node_id': {'type': 'string', 'enum': [node_id]},
            'connection': {'type': 'string', 'minLength': 10, 'maxLength': 450}},
        'required': ['node_id', 'connection']}
