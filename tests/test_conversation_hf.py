"""Le format de chat marche aussi avec le tokenizer 8 192 de la compétition et un contexte de 512."""
from pathlib import Path

import pytest
import torch

from minigpt.bpe import BPETokenizer
from minigpt.conversation import prompt_ids, reply, supervised_examples
from minigpt.hf_tokenizer import HFTokenizer, load_tokenizer
from minigpt.model import GPT, GPTConfig

# Le tokenizer est une donnée hors git : les tests sont sautés s'il est absent.
ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = [ROOT / 'data/processed/ablation-extra/tokenizer.json',
              ROOT.parents[1] / 'data/processed/ablation-extra/tokenizer.json']
TOK_PATH = next((p for p in CANDIDATES if p.exists()), None)
needs_tok = pytest.mark.skipif(TOK_PATH is None, reason='tokenizer.json 8 192 absent')


@needs_tok
def test_load_tokenizer_detects_format(tmp_path):
    # Fichier Hugging Face -> HFTokenizer ; fichier du BPE maison -> BPETokenizer.
    assert isinstance(load_tokenizer(TOK_PATH), HFTokenizer)
    bpe_path = tmp_path / 'bpe.json'
    BPETokenizer().save(bpe_path)
    assert isinstance(load_tokenizer(bpe_path), BPETokenizer)


@needs_tok
def test_prompt_keeps_512_tokens_and_ends_with_header():
    tok = load_tokenizer(TOK_PATH)
    history = [('user', 'ancien propos ' * 400), ('assistant', 'bonjour'), ('user', 'suite')]
    ids, dropped = prompt_ids(tok, history, 512)
    assert len(ids) == 512 and dropped > 0
    assert tok.decode(ids).endswith('VOUS.\nsuite\n\nMOI.\n')


@needs_tok
def test_supervised_targets_decode_to_answer_with_hf():
    tok = load_tokenizer(TOK_PATH)
    history = [('user', 'Salut.'), ('assistant', 'Bonjour, mon ami.'), ('user', 'Et vous ?'), ('assistant', 'Fort bien.')]
    first, second = supervised_examples(tok, history, 512)
    # Les cibles reconstituent exactement la réponse et sa fin de réplique.
    assert tok.decode(first[1][first[1] != -100].tolist()) == 'Bonjour, mon ami.\n\n'
    x, y = second
    offset = (y != -100).nonzero()[0].item()
    assert tok.decode(x[:offset + 1].tolist()).endswith('VOUS.\nEt vous ?\n\nMOI.\n')


class ScriptedModel(torch.nn.Module):
    """Faux modèle qui émet une suite de tokens fixée, pour tester l'arrêt de reply."""

    def __init__(self, tokens, vocab):
        super().__init__()
        self.cfg = GPTConfig(vocab_size=vocab, block_size=512, n_layer=1, n_head=1, d_model=8)
        self.tokens, self.vocab, self.calls = tokens, vocab, 0
        self.anchor = torch.nn.Parameter(torch.zeros(1))  # donne un appareil au faux modèle

    def forward(self, idx):
        logits = torch.full((1, idx.shape[1], self.vocab), -1e9)
        logits[0, -1, self.tokens[min(self.calls, len(self.tokens) - 1)]] = 0.0
        self.calls += 1
        return logits, None


@needs_tok
def test_reply_stops_at_double_newline_with_hf():
    tok = load_tokenizer(TOK_PATH)
    # Le texte complet est tokenisé d'un bloc : "\n\n" peut être fusionné avec d'autres caractères.
    scripted = tok.encode('Fort bien, mon ami.\n\nVOUS.\nEncore')
    result = reply(ScriptedModel(scripted, len(tok.vocab)), tok, [('user', 'Bonjour')], max_tokens=50)
    assert result['text'] == 'Fort bien, mon ami.'
    assert result['generated_tokens'] < len(scripted)  # arrêt avant la suite
