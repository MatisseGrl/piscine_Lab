"""Mesure si interpoler les poids limite la dégradation du BPB sans perdre le dialogue."""
import argparse
import hashlib
from pathlib import Path

import torch

from minigpt.bigram import load_utf8
from minigpt.bpe import BPETokenizer
from minigpt.chat_bench import DEV
from minigpt.chat_sft import evaluate_dialogues
from minigpt.finetune import restore_model, write_json
from minigpt.model import evaluate_bpb


def main():
    """Compare des interpolations sur le développement, avec validation Molière séparée."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'chat', 'tokenizer', 'validation', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(2)
    base = torch.load(args.base, map_location='cpu', weights_only=True)
    chat = torch.load(args.chat, map_location='cpu', weights_only=True)
    tokenizer = BPETokenizer.load(args.tokenizer)
    validation = load_utf8(args.validation)
    base_hash = hashlib.sha256(args.base.read_bytes()).hexdigest()
    if base_hash != chat['chat_sft']['parent_sha256'] or base['config'] != chat['config']:
        raise ValueError('La base doit être le checkpoint parent du SFT.')
    if hashlib.sha256(validation).hexdigest() != base['val_sha256']:
        raise ValueError('Validation différente de celle du checkpoint de départ.')
    if hashlib.sha256(args.tokenizer.read_bytes()).hexdigest() != chat['chat_sft']['tokenizer_sha256']:
        raise ValueError('Tokenizer différent de celui du SFT.')
    text = validation.decode('utf-8')
    ids = tokenizer.encode(text)
    args.out.mkdir(parents=True, exist_ok=False)
    for fraction in [0.75, 0.9]:
        # Les poids ont la même architecture et le même parent : correspondance terme à terme.
        weights = {key: torch.lerp(base['model'][key], tensor, fraction) for key, tensor in chat['model'].items()}
        result = {'config': chat['config'], 'model': weights, 'val_sha256': base['val_sha256'],
                  'interpolation': {'chat_fraction': fraction, 'parent_sha256': base_hash,
                                    'chat_sha256': hashlib.sha256(args.chat.read_bytes()).hexdigest(),
                                    'chat_step': chat['step'],
                                    'tokenizer_sha256': chat['chat_sft']['tokenizer_sha256']}}
        model = restore_model(result)
        result['val_bpb'] = evaluate_bpb(model, ids, text)
        name = f'mix-{int(fraction * 100)}'
        torch.save(result, args.out / f'{name}.pt')
        write_json(args.out / f'{name}.json', {'bpb': result['val_bpb'], 'discussions': evaluate_dialogues(model, tokenizer, DEV)})
        print(f"{name} : {result['val_bpb']:.6f} BPB", flush=True)


if __name__ == '__main__':
    main()
