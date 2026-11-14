"""Compare les générations de plusieurs checkpoints sur un lot réservé."""
import argparse
import hashlib
from pathlib import Path
import torch
from minigpt.bpe import BPETokenizer
from minigpt.bigram import load_utf8
from minigpt.finetune import restore_model, write_json
from minigpt.chat_sft import evaluate_dialogues
from minigpt.chat_bench import DEV, FINAL
from minigpt.conversation import HEADERS
from minigpt.model import evaluate_bpb
from minigpt.repair_bench import REPAIR_DEV, REPAIR_FINAL, evaluate_repairs


def main():
    """Enregistre les tours sans filtrer les erreurs ni remplacer les réponses."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoints', nargs='+', type=Path, required=True)
    parser.add_argument('--tokenizer', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--split', choices=['dev', 'final'], default='dev')
    parser.add_argument('--repair', action='store_true')
    parser.add_argument('--validation', type=Path)
    parser.add_argument('--roles', choices=['demo', 'legacy'], default='demo')
    args = parser.parse_args()
    # Le diagnostic historique conserve les noms appris par le pilote de la PR #18.
    headers = HEADERS if args.roles == 'demo' else {'user': 'SGANARELLE.\n', 'assistant': 'DON JUAN.\n'}
    args.out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(2)
    tokenizer = BPETokenizer.load(args.tokenizer)
    # Le BPB facultatif réutilise strictement les octets de validation du checkpoint.
    validation = load_utf8(args.validation) if args.validation else None
    val_text = validation.decode('utf-8') if validation else None
    val_ids = tokenizer.encode(val_text) if val_text else None
    for index, checkpoint in enumerate(args.checkpoints):
        saved = torch.load(checkpoint, weights_only=True, map_location='cpu')
        model = restore_model(saved)
        results = evaluate_dialogues(model, tokenizer, DEV if args.split == 'dev' else FINAL, headers=headers)
        bpb = saved['val_bpb']
        if validation:
            if hashlib.sha256(validation).hexdigest() != saved['val_sha256']:
                raise ValueError('Validation différente de celle du checkpoint.')
            bpb = evaluate_bpb(model, val_ids, val_text)
        write_json(args.out / f'{index}-{checkpoint.stem}.json', {
            'checkpoint': str(checkpoint), 'checkpoint_sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            'split': args.split, 'roles': args.roles, 'bpb': bpb, 'bpb_recomputed': bool(validation),
            'discussions': results,
            'repairs': evaluate_repairs(model, tokenizer, REPAIR_DEV if args.split == 'dev' else REPAIR_FINAL) if args.repair else [],
        })
        print(str(checkpoint), flush=True)


if __name__ == '__main__':
    main()
