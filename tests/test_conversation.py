"""Vérifications du format commun et de la supervision des réponses."""
import torch
from minigpt.bpe import BPETokenizer
from minigpt.conversation import prompt_ids, supervised_examples


def test_history_and_overflow():
    """Le contexte conserve les derniers octets et les rôles sans dépasser la fenêtre."""
    tok = BPETokenizer()
    history = [('user', 'ancien ' * 40), ('assistant', 'bonjour'), ('user', 'suite')]
    ids, dropped = prompt_ids(tok, history, 128)
    assert len(ids) == 128 and dropped > 0
    assert tok.decode(ids).endswith('VOUS.\nsuite\n\nMOI.\n')


def test_response_targets():
    """Le premier token et la fin de réponse sont appris, jamais la question."""
    tok = BPETokenizer()
    examples = supervised_examples(tok, [('user', 'a'), ('assistant', 'bc')], 128)
    x, y = examples[0]
    assert y[y != -100].tolist() == tok.encode('bc\n\n')
    first = (y != -100).nonzero()[0].item()
    assert x[first].item() == ord('\n')
    logits = torch.randn(1, 128, 256, requires_grad=True)
    torch.nn.functional.cross_entropy(logits.view(-1, 256), y).backward()
    assert logits.grad[0, :first].abs().sum() == 0


def test_long_response_is_fully_supervised():
    """Une réponse longue passe en fenêtres sans perdre ses cibles."""
    tok = BPETokenizer()
    examples = supervised_examples(tok, [('user', 'a'), ('assistant', 'b' * 160)], 128)
    assert sum((y != -100).sum().item() for _, y in examples) == 162


def test_second_response_uses_first_exchange():
    """Au deuxième tour, les entrées d'entraînement contiennent aussi la première réponse."""
    tok = BPETokenizer()
    history = [('user', 'Salut.'), ('assistant', 'Bonjour.'), ('user', 'Et vous ?'), ('assistant', 'Bien.')]
    first, second = supervised_examples(tok, history, 128)
    x, y = second
    # Le préfixe du deuxième exemple correspond au texte que le serveur voit avant génération.
    expected = 'VOUS.\nSalut.\n\nMOI.\nBonjour.\n\nVOUS.\nEt vous ?\n\nMOI.\n'
    offset = (y != -100).nonzero()[0].item()
    assert tok.decode(x[:offset + 1].tolist()) == expected
    assert y[y != -100].tolist() == tok.encode('Bien.\n\n')
    assert first[1][first[1] != -100].tolist() == tok.encode('Bonjour.\n\n')
