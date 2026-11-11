"""Format multi-tour commun au SFT et à la démo, sans moteur de réponses externe."""
import torch

HEADERS = {'user': 'VOUS.\n', 'assistant': 'MOI.\n'}


def format_history(history, headers=HEADERS):
    """Sérialise les rôles sans changer le texte de l'interlocuteur."""
    return ''.join(headers[role] + text.strip() + '\n\n' for role, text in history)


def prompt_ids(tokenizer, history, size=128, headers=HEADERS):
    """Garde la fin du contexte exactement comme la fenêtre glissante du modèle."""
    ids = tokenizer.encode(format_history(history, headers) + headers['assistant'])
    # Le compte exclu sert à signaler à la page la perte des premières répliques.
    return ids[-size:], max(0, len(ids) - size)


def supervised_examples(tokenizer, history, size=128):
    """Supervise chaque réponse avec son historique et découpe les réponses longues."""
    examples = []
    for index, (role, text) in enumerate(history):
        if role != 'assistant':
            continue
        prefix, _ = prompt_ids(tokenizer, history[:index], size)
        answer = tokenizer.encode(text.strip() + '\n\n')
        # Les fenêtres successives conservent les tokens de réponse déjà produits.
        for offset in range(0, len(answer), 32):
            target = answer[offset:offset + 32]
            context = (prefix + answer[:offset])[-(size + 1 - len(target)):]
            sequence = context + target
            x = torch.zeros(size, dtype=torch.long)
            y = torch.full((size,), -100, dtype=torch.long)
            x[:len(sequence) - 1] = torch.tensor(sequence[:-1])
            # La dernière position du préfixe prédit le premier token de la réponse.
            y[len(context) - 1:len(sequence) - 1] = torch.tensor(target)
            examples.append((x, y))
    return examples


@torch.inference_mode()
def reply(model, tokenizer, history, max_tokens=80, temperature=0.0, seed=42, *, headers=HEADERS):
    """Produit uniquement des tokens du modèle et s'arrête à la fin de réplique."""
    ids, dropped = prompt_ids(tokenizer, history, model.cfg.block_size, headers)
    context = torch.tensor([ids], dtype=torch.long)
    generated = []
    generator = torch.Generator().manual_seed(seed)
    model.eval()
    for _ in range(max_tokens):
        # La fenêtre glisse aussi pendant la génération, token après token.
        logits, _ = model(context[:, -model.cfg.block_size:])
        if temperature == 0:
            token = logits[:, -1].argmax(-1, keepdim=True)
        else:
            token = torch.multinomial(torch.softmax(logits[:, -1] / temperature, -1), 1, generator=generator)
        generated.append(token.item())
        context = torch.cat((context, token), dim=1)
        raw = tokenizer.decode(generated)
        if '\n\n' in raw:
            break
    raw = tokenizer.decode(generated)
    return {'text': raw.split('\n\n', 1)[0].strip(), 'raw': raw,
            'dropped_tokens': dropped, 'generated_tokens': len(generated)}
