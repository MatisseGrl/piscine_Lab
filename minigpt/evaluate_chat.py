"""Compare les générations de plusieurs checkpoints sur un lot réservé."""
import argparse
import hashlib
import json
from pathlib import Path
import torch
from minigpt.hf_tokenizer import load_tokenizer
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
    parser.add_argument('--bench', type=Path, help='Lot externe au format conversations/turns.')
    parser.add_argument('--bpb-only', action='store_true')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--roles', choices=['demo', 'legacy'], default='demo')
    args = parser.parse_args()
    # Le diagnostic historique conserve les noms appris par le pilote de la PR #18.
    headers = HEADERS if args.roles == 'demo' else {'user': 'SGANARELLE.\n', 'assistant': 'DON JUAN.\n'}
    args.out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(2)
    tokenizer = load_tokenizer(args.tokenizer)
    discussions = DEV if args.split == 'dev' else FINAL
    if args.bench:
        bench = json.loads(args.bench.read_text(encoding='utf-8-sig'))
        discussions = [conversation['turns'] for conversation in bench['conversations']]
    # Vérifie le tokenizer et la validation avant de produire la première réponse.
    tokenizer_hash = hashlib.sha256(args.tokenizer.read_bytes()).hexdigest()
    # Le BPB facultatif réutilise strictement les octets de validation du checkpoint.
    validation = load_utf8(args.validation) if args.validation else None
    val_text = validation.decode('utf-8') if validation else None
    val_ids = tokenizer.encode(val_text) if val_text else None
    for index, checkpoint in enumerate(args.checkpoints):
        saved = torch.load(checkpoint, weights_only=True, map_location='cpu')
        expected_tokenizer = saved.get('tokenizer_sha256') or saved.get('pretrain', {}).get('tokenizer_sha256')
        if expected_tokenizer and expected_tokenizer != tokenizer_hash:
            raise ValueError('Tokenizer différent de celui du checkpoint.')
        model = restore_model(saved).to(args.device)
        bpb = saved.get('val_bpb')
        if validation:
            if 'val_sha256' in saved and hashlib.sha256(validation).hexdigest() != saved['val_sha256']:
                raise ValueError('Validation différente de celle du checkpoint.')
            bpb = evaluate_bpb(model, val_ids, val_text)
        results = [] if args.bpb_only else evaluate_dialogues(model, tokenizer, discussions, headers=headers)
        write_json(args.out / f'{index}-{checkpoint.stem}.json', {
            'checkpoint': str(checkpoint), 'checkpoint_sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            'split': args.split, 'roles': args.roles, 'bpb': bpb, 'bpb_recomputed': bool(validation),
            'bench_sha256': hashlib.sha256(args.bench.read_bytes()).hexdigest() if args.bench else None,
            'discussions': results,
            'repairs': evaluate_repairs(model, tokenizer, REPAIR_DEV if args.split == 'dev' else REPAIR_FINAL) if args.repair else [],
        })
        print(str(checkpoint), flush=True)


if __name__ == '__main__':
    main()
