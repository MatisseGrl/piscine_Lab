"""Pilote supervisé sur les seules répliques authentiques du train Molière."""

import argparse
import hashlib
import json
import re
from pathlib import Path

import torch

from minigpt.bigram import CORPUS, load_utf8
from minigpt.bpe import BPETokenizer
from minigpt.finetune import restore_model, write_json
from minigpt.model import evaluate_bpb

# Ces questions modernes sont réservées à l'évaluation, sans réponse cible apprise.
HELD_OUT = [
    "Bonjour monsieur, êtes-vous de bonne humeur ce matin ?",
    "Dites-moi, comment vous portez-vous aujourd'hui ?",
    "Je vous salue, voulez-vous bien me saluer aussi ?",
    "Quel nom dois-je employer pour vous appeler, monsieur ?",
    "Je suis fort triste ce soir, pouvez-vous me consoler ?",
    "Accepteriez-vous de m'aider dans une petite affaire ?",
    "Je vous remercie de votre aide, mon cher ami.",
    "Il est temps pour moi de partir, je vous souhaite une bonne soirée.",
]


def format_prompt(question: str) -> str:
    """Reproduit exactement le format déjà employé dans minigpt.chat."""
    return f"SGANARELLE.\n{question}\n\nDON JUAN.\n"


def extract_pairs(text: str) -> list[tuple[str, str]]:
    """Garde deux répliques consécutives sans traverser une scène ou une didascalie."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    header = re.compile(r"[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ .’'\-]{1,45}\.")

    def is_speaker(value: str) -> bool:
        """Écarte notamment les titres de scène et les actes."""
        return bool(header.fullmatch(value)) and not value.startswith(("SCÈNE", "ACTE"))

    pairs = []
    for index in range(len(paragraphs) - 3):
        first, question, second, answer = paragraphs[index:index + 4]
        if not (is_speaker(first) and is_speaker(second)) or first == second:
            continue
        # Aucun texte n'est inventé : seule la remise en ligne des vers est faite.
        question, answer = " ".join(question.split()), " ".join(answer.split())
        if all(re.search(r"[a-zà-öø-ÿ]", value) for value in [question, answer]):
            pairs.append((question, answer))
    return list(dict.fromkeys(pairs))


def masked_example(prompt: list[int], answer: list[int], size: int) -> tuple[torch.Tensor, torch.Tensor]:
    """Décale les cibles, masque le prompt et le padding avec ignore_index=-100."""
    sequence = prompt + answer
    if not prompt or not answer or len(sequence) - 1 > size:
        raise ValueError("Exemple vide ou trop long : aucune troncature silencieuse.")
    x = torch.zeros(size, dtype=torch.long)
    y = torch.full((size,), -100, dtype=torch.long)
    x[:len(sequence) - 1] = torch.tensor(sequence[:-1])
    # La position précédant la réponse prédit son premier token.
    y[len(prompt) - 1:len(sequence) - 1] = torch.tensor(answer)
    return x, y


def generations(model, tokenizer: BPETokenizer) -> list[dict]:
    """Produit les vraies sorties avec les mêmes graines et paramètres que la démo."""
    records = []
    for question in ["bonjour", "tu vas bien ?"] + HELD_OUT:
        start = torch.tensor([tokenizer.encode(format_prompt(question))])
        generator = torch.Generator().manual_seed(42)
        output = model.generate(start, 80, temperature=0.7, generator=generator)
        raw = tokenizer.decode(output[0, start.shape[1]:].tolist())
        records.append({"question": question, "held_out": question in HELD_OUT,
                        "raw": raw, "displayed": raw.split("\n\n", 1)[0].strip()})
    return records


def main() -> None:
    """Entraîne un pilote à durée fixée, puis mesure BPB et conversation séparément."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=400)
    args = parser.parse_args()
    if args.steps < 1:
        parser.error("Le nombre de pas doit être positif.")
    args.out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    torch.manual_seed(2026)
    saved = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = restore_model(saved)
    tokenizer = BPETokenizer.load(args.tokenizer)
    train_bytes = load_utf8(CORPUS / "moliere_train.txt")
    if hashlib.sha256(train_bytes).hexdigest() != saved["train_sha256"]:
        raise ValueError("Le corpus diffère du corpus de référence.")
    text = train_bytes.decode("utf-8")
    normalized = " ".join(text.casefold().split())
    # Vérifie que les questions inédites n'étaient même pas dans le préentraînement.
    for question in HELD_OUT:
        if " ".join(question.casefold().split()) in normalized:
            raise ValueError("Une question réservée au test apparaît dans le train.")
    examples, sources = [], []
    for question, answer in extract_pairs(text):
        prompt = tokenizer.encode(format_prompt(question))
        response = tokenizer.encode(answer + "\n\n")
        if len(prompt) + len(response) - 1 <= model.cfg.block_size:
            examples.append(masked_example(prompt, response, model.cfg.block_size))
            sources.append({"question": question, "answer": answer})
    if not examples:
        raise ValueError("Aucune paire exploitable.")
    write_json(args.out / "pairs.json", sources)
    write_json(args.out / "test_questions.json", HELD_OUT)
    pair_hash = hashlib.sha256((args.out / "pairs.json").read_bytes()).hexdigest()
    metadata = {"source": "moliere_train.txt", "source_sha256": saved["train_sha256"],
                "pairs": len(examples), "pairs_sha256": pair_hash, "steps": args.steps,
                "seed": 2026, "lr": 5e-5, "batch_size": 16, "loss": "response_only",
                "parent_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                "tokenizer_sha256": hashlib.sha256(args.tokenizer.read_bytes()).hexdigest(),
                "synthetic_training_text": False, "prompt_format": format_prompt("{question}")}
    write_json(args.out / "manifest.json", metadata)
    print(f"Paires authentiques retenues : {len(examples)}", flush=True)
    # Les sorties sont enregistrées avant de consulter leur qualité : pas de sélection des meilleurs exemples.
    original = restore_model(torch.load(args.reference, map_location="cpu", weights_only=True))
    write_json(args.out / "original.json", generations(original, tokenizer))
    write_json(args.out / "before.json", generations(model, tokenizer))
    x = torch.stack([example[0] for example in examples])
    y = torch.stack([example[1] for example in examples])
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)
    generator = torch.Generator().manual_seed(2026)
    losses = []
    model.train()
    for step in range(1, args.steps + 1):
        indices = torch.randint(len(examples), (16,), generator=generator)
        optimizer.zero_grad(set_to_none=True)
        _, loss = model(x[indices], y[indices])
        loss.backward()
        optimizer.step()
        losses.append(loss.item())
        if step % 100 == 0:
            print(f"SFT {step}/{args.steps}, loss réponse={sum(losses[-100:]) / len(losses[-100:]):.4f}", flush=True)
    # La validation du kit ne sert jamais à fabriquer les paires ni à calculer les gradients.
    val_bytes = load_utf8(CORPUS / "moliere_val.txt")
    if hashlib.sha256(val_bytes).hexdigest() != saved["val_sha256"]:
        raise ValueError("La validation diffère de la référence.")
    val_text = val_bytes.decode("utf-8")
    bpb = evaluate_bpb(model, tokenizer.encode(val_text), val_text)
    torch.save({**saved, "model": model.state_dict(), "val_bpb": bpb,
                "optimizer": optimizer.state_dict(), "sft": metadata,
                "rng_state": torch.get_rng_state(), "batch_rng_state": generator.get_state()}, args.out / "dialogue.pt")
    write_json(args.out / "after.json", generations(model, tokenizer))
    write_json(args.out / "result.json", {"val_bpb": bpb, "parent_bpb": saved["val_bpb"], "losses": losses})
    print(f"BPB après SFT : {bpb:.6f}. Pertinence à évaluer séparément.", flush=True)


if __name__ == "__main__":
    main()
