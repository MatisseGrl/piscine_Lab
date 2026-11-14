"""SFT multi-tour reproductible du mini-GPT existant avec rappel Molière facultatif."""
import argparse
import hashlib
import json
import time
from pathlib import Path
import torch
from minigpt.bpe import BPETokenizer
from minigpt.bigram import load_utf8
from minigpt.finetune import restore_model, write_json
from minigpt.conversation import HEADERS, supervised_examples, reply
from minigpt.chat_bench import DEV, FINAL
from minigpt.repair_bench import REPAIR_DEV, REPAIR_FINAL, evaluate_repairs
from minigpt.model import evaluate_bpb
from minigpt.train import sample_batch


def evaluate_dialogues(model, tokenizer, discussions, *, headers=HEADERS):
    """Conserve toutes les réponses dans des discussions réellement autorégressives."""
    outputs = []
    for discussion in discussions:
        history, turns = [], []
        for question in discussion:
            history.append(('user', question))
            result = reply(model, tokenizer, history, headers=headers)
            history.append(('assistant', result['text']))
            turns.append({'question': question, **result})
        outputs.append(turns)
    return outputs


def main():
    """Entraîne, mesure et sauvegarde chaque palier sans consulter le test final."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['checkpoint', 'tokenizer', 'data', 'corpus', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--repair-bench', action='store_true')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--steps', type=int, default=600)
    parser.add_argument('--lr', type=float, default=3e-4)
    parser.add_argument('--replay', type=float, default=0.1)
    parser.add_argument('--every', type=int, default=300)
    args = parser.parse_args()
    if args.steps < 1 or args.every < 1 or args.lr <= 0 or not 0 <= args.replay < 1:
        parser.error('Pas, fréquence et taux positifs ; rappel entre 0 inclus et 1 exclu.')
    args.out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(args.threads)
    torch.manual_seed(20261111)
    generator = torch.Generator().manual_seed(20261111)
    saved = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    model = restore_model(saved)
    tokenizer = BPETokenizer.load(args.tokenizer)
    records = json.loads(args.data.read_text(encoding='utf-8'))
    train_text = load_utf8(args.corpus / 'moliere_train.txt').decode('utf-8')
    val_text = load_utf8(args.corpus / 'moliere_val.txt').decode('utf-8')
    # Les corpus sont liés aux poids par leurs octets UTF-8 normalisés.
    for name, text in [('train', train_text), ('val', val_text)]:
        if hashlib.sha256(text.encode('utf-8')).hexdigest() != saved[name + '_sha256']:
            raise ValueError('Corpus différent de la référence : ' + name)
    normalized = ' '.join((train_text + json.dumps(records, ensure_ascii=False)).casefold().split())
    # Aucun prompt des lots réservés ne doit se trouver dans les textes appris.
    for discussion in DEV + FINAL + [[case[2]] for case in REPAIR_DEV + REPAIR_FINAL]:
        for question in discussion:
            if ' '.join(question.casefold().split()) in normalized:
                raise ValueError(f'Question réservée présente au train : {question}')
    # Un mauvais tour présent dans un scénario de réparation reste une simple entrée.
    examples = [example for record in records for example in supervised_examples(
        tokenizer, record['messages'], model.cfg.block_size, last_only=record.get('last_only', False))]
    x, y = [torch.stack([example[i] for example in examples]) for i in range(2)]
    train_ids = torch.tensor(tokenizer.encode(train_text), dtype=torch.long)
    val_ids = tokenizer.encode(val_text)
    metadata = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    metadata.update({'seed': 20261111, 'batch_size': 32, 'examples': len(examples),
                     'data_sha256': hashlib.sha256(args.data.read_bytes()).hexdigest(),
                     'parent_sha256': hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                     'tokenizer_sha256': hashlib.sha256(args.tokenizer.read_bytes()).hexdigest()})
    write_json(args.out / 'manifest.json', metadata)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    losses, measures = [], []
    response_tokens_seen, replay_tokens_seen = 0, 0
    started = time.monotonic()
    for step in range(1, args.steps + 1):
        model.train()
        # Un rappel de langue réduit l'oubli ; sa proportion est explicite et mesurable.
        indices = torch.randint(len(examples), (32,), generator=generator)
        response_tokens_seen += int((y[indices] != -100).sum())
        replay_tokens_seen += 8 * model.cfg.block_size if args.replay else 0
        optimizer.zero_grad(set_to_none=True)
        _, chat_loss = model(x[indices], y[indices])
        loss = chat_loss
        if args.replay:
            _, replay_loss = model(*sample_batch(train_ids, 8, model.cfg.block_size, generator))
            loss = (1 - args.replay) * chat_loss + args.replay * replay_loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        losses.append(chat_loss.item())
        if step % 100 == 0:
            print(f'Pas {step} loss réponse {sum(losses[-100:])/len(losses[-100:]):.4f}', flush=True)
        if step % args.every == 0 or step == args.steps:
            bpb = evaluate_bpb(model, val_ids, val_text)
            torch.save({**saved, 'model': model.state_dict(), 'val_bpb': bpb,
                        'chat_sft': metadata, 'step': step, 'optimizer': optimizer.state_dict(),
                        'rng_state': torch.get_rng_state(), 'batch_rng_state': generator.get_state()}, args.out / f'step-{step}.pt')
            write_json(args.out / f'dev-{step}.json', evaluate_dialogues(model, tokenizer, DEV))
            if args.repair_bench:
                write_json(args.out / f'repair-{step}.json', evaluate_repairs(model, tokenizer, REPAIR_DEV))
            measures.append({'step': step, 'bpb': bpb, 'response_loss': sum(losses[-100:])/len(losses[-100:]), 'response_tokens_seen': response_tokens_seen, 'replay_tokens_seen': replay_tokens_seen, 'seconds': time.monotonic()-started})
            write_json(args.out / 'measures.json', measures)
            write_json(args.out / 'losses.json', losses)
            print(json.dumps(measures[-1]), flush=True)


if __name__ == '__main__':
    main()
