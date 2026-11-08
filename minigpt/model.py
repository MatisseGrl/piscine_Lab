"""Transformer décodeur (type GPT) écrit à la main en PyTorch.

Briques : embeddings de tokens + positions, blocs [LayerNorm -> attention causale multi-têtes
-> résiduel, LayerNorm -> MLP -> résiduel], LayerNorm finale, tête linéaire vers le vocabulaire.
L'attention et le masque causal sont codés à la main (pas de nn.MultiheadAttention ni de
scaled_dot_product_attention). On s'autorise nn.Linear et nn.Embedding (de simples matrices).
"""

import math
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class GPTConfig:
    """Hyperparamètres du modèle. Valeurs par défaut : config CPU pour Molière (~1,1 M paramètres)."""

    vocab_size: int = 1024  # taille du vocabulaire BPE (bpe_moliere_1024.json)
    block_size: int = 128  # longueur de contexte maximale, en tokens (~320 octets)
    n_layer: int = 4  # nombre de blocs Transformer
    n_head: int = 4  # nombre de têtes d'attention
    d_model: int = 128  # dimension des vecteurs (embeddings et flux résiduel)
    dropout: float = 0.0  # dropout (0 = désactivé)


class LayerNorm(nn.Module):
    """Normalisation par couche : centre et réduit chaque vecteur sur sa dernière dimension,
    puis applique un gain (weight) et un décalage (bias) appris."""

    def __init__(self, d: int, eps: float = 1e-5):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(d))  # gain, initialisé à 1
        self.bias = nn.Parameter(torch.zeros(d))  # décalage, initialisé à 0
        self.eps = eps  # évite la division par zéro

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        mean = x.mean(dim=-1, keepdim=True)  # moyenne sur les features
        var = x.var(dim=-1, keepdim=True, unbiased=False)  # variance biaisée, comme PyTorch
        x_hat = (x - mean) / torch.sqrt(var + self.eps)  # moyenne 0, variance 1
        return x_hat * self.weight + self.bias


class CausalSelfAttention(nn.Module):
    """Attention multi-têtes avec masque causal : chaque position ne regarde que le passé."""

    def __init__(self, cfg: GPTConfig):
        super().__init__()
        if cfg.d_model % cfg.n_head != 0:
            raise ValueError("d_model doit être divisible par n_head")
        self.n_head = cfg.n_head
        self.head_dim = cfg.d_model // cfg.n_head
        # Une seule matrice produit Q, K et V d'un coup (3 * d_model sorties).
        self.qkv = nn.Linear(cfg.d_model, 3 * cfg.d_model)
        # Projection de sortie : remélange les têtes concaténées.
        self.proj = nn.Linear(cfg.d_model, cfg.d_model)
        self.attn_drop = nn.Dropout(cfg.dropout)
        self.resid_drop = nn.Dropout(cfg.dropout)
        # Masque triangulaire inférieur : mask[i, j] = 1 si j <= i (j est dans le passé de i).
        # Buffer = sauvegardé avec le modèle mais pas appris.
        mask = torch.tril(torch.ones(cfg.block_size, cfg.block_size, dtype=torch.bool))
        self.register_buffer("mask", mask, persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape  # batch, longueur, dimension
        q, k, v = self.qkv(x).split(C, dim=2)  # trois tenseurs (B, T, C)
        # Découpage en têtes : (B, T, C) -> (B, n_head, T, head_dim).
        q = q.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_head, self.head_dim).transpose(1, 2)
        # Scores : similarité de chaque requête avec chaque clé, divisée par sqrt(head_dim)
        # pour que la softmax ne sature pas quand la dimension grandit. Forme (B, h, T, T).
        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        # Masque causal : les positions futures reçoivent -inf, donc un poids 0 après softmax.
        att = att.masked_fill(~self.mask[:T, :T], float("-inf"))
        att = F.softmax(att, dim=-1)  # chaque ligne somme à 1 : poids sur les positions passées
        att = self.attn_drop(att)
        y = att @ v  # moyenne pondérée des valeurs, (B, h, T, head_dim)
        # Recolle les têtes : (B, h, T, hd) -> (B, T, C).
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.resid_drop(self.proj(y))


class MLP(nn.Module):
    """Réseau position par position : élargit à 4 * d_model, GELU, puis revient à d_model."""

    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.fc = nn.Linear(cfg.d_model, 4 * cfg.d_model)
        self.proj = nn.Linear(4 * cfg.d_model, cfg.d_model)
        self.drop = nn.Dropout(cfg.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.drop(self.proj(F.gelu(self.fc(x))))


class Block(nn.Module):
    """Bloc Transformer pre-norm : x + attn(LN(x)), puis x + mlp(LN(x))."""

    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.ln1 = LayerNorm(cfg.d_model)
        self.attn = CausalSelfAttention(cfg)
        self.ln2 = LayerNorm(cfg.d_model)
        self.mlp = MLP(cfg)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Connexions résiduelles : chaque sous-couche ajoute une correction au flux x,
        # ce qui laisse passer le gradient directement jusqu'aux premières couches.
        x = x + self.attn(self.ln1(x))  # communication entre positions
        x = x + self.mlp(self.ln2(x))  # calcul sur chaque position
        return x


class GPT(nn.Module):
    """Modèle de langue décodeur : prédit le token suivant à chaque position."""

    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.cfg = cfg
        self.tok_emb = nn.Embedding(cfg.vocab_size, cfg.d_model)  # un vecteur par token
        self.pos_emb = nn.Embedding(cfg.block_size, cfg.d_model)  # un vecteur par position
        self.drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList([Block(cfg) for _ in range(cfg.n_layer)])
        self.ln_f = LayerNorm(cfg.d_model)  # LayerNorm finale
        self.head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)  # vers les logits
        self.apply(self._init_weights)

    @staticmethod
    def _init_weights(module: nn.Module) -> None:
        """Initialisation façon GPT-2 : poids N(0, 0.02), biais à 0."""
        if isinstance(module, (nn.Linear, nn.Embedding)):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
        if isinstance(module, nn.Linear) and module.bias is not None:
            nn.init.zeros_(module.bias)

    def num_params(self) -> int:
        """Nombre total de paramètres appris."""
        return sum(p.numel() for p in self.parameters())

    def forward(
        self, idx: torch.Tensor, targets: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, torch.Tensor | None]:
        """idx : ids (B, T). Renvoie les logits (B, T, V) et, si targets est donné,
        la cross-entropie moyenne en nats par token."""
        B, T = idx.shape
        if T > self.cfg.block_size:
            raise ValueError(f"séquence de {T} tokens > contexte de {self.cfg.block_size}")
        pos = torch.arange(T, device=idx.device)  # positions 0..T-1
        x = self.drop(self.tok_emb(idx) + self.pos_emb(pos))  # (B, T, C), positions diffusées sur B
        for block in self.blocks:
            x = block(x)
        logits = self.head(self.ln_f(x))  # (B, T, V)
        loss = None
        if targets is not None:
            # Cross-entropie = -log p(token cible), moyennée sur toutes les positions.
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.reshape(-1))
        return logits, loss

    @torch.no_grad()
    def generate(
        self,
        idx: torch.Tensor,
        max_new_tokens: int,
        temperature: float = 1.0,
        generator: torch.Generator | None = None,
    ) -> torch.Tensor:
        """Ajoute max_new_tokens tokens à idx (B, T) par échantillonnage.
        temperature < 1 : plus prudent, > 1 : plus varié. generator : graine pour reproduire."""
        if temperature <= 0:
            raise ValueError("temperature doit être > 0")
        was_training = self.training
        self.eval()  # pas de dropout pendant la génération
        for _ in range(max_new_tokens):
            ctx = idx[:, -self.cfg.block_size :]  # on ne garde que les derniers tokens du contexte
            logits, _ = self(ctx)
            logits = logits[:, -1, :] / temperature  # seule la dernière position prédit la suite
            probs = F.softmax(logits, dim=-1)
            nxt = torch.multinomial(probs, num_samples=1, generator=generator)  # (B, 1)
            idx = torch.cat([idx, nxt], dim=1)
        self.train(was_training)
        return idx


def bits_per_byte(nll_nats: float, text: str) -> float:
    """BPB = bits totaux / nombre d'octets UTF-8 du texte (pas de caractères, pas de tokens).
    nll_nats : somme des -ln p sur tous les tokens prédits."""
    n_bytes = len(text.encode("utf-8"))
    return nll_nats / math.log(2) / n_bytes


@torch.no_grad()
def evaluate_bpb(model: GPT, ids: list[int], text: str) -> float:
    """BPB du modèle sur un texte déjà encodé (ids = tokenizer.encode(text)).

    On découpe ids en fenêtres consécutives (la cible de l'une est l'entrée de la suivante) : chaque fenêtre prédit
    block_size tokens. Tous les tokens sauf le premier sont donc prédits une fois (le premier
    n'a pas de contexte, son coût est négligeable sur un long texte). Les bits sont divisés par
    les octets UTF-8 de tout le texte."""
    was_training = model.training
    model.eval()
    T = model.cfg.block_size
    data = torch.tensor(ids, dtype=torch.long)
    # Débuts des fenêtres : 0, T, 2T, ... ; chaque fenêtre lit [s, s+T] (T+1 tokens).
    starts = list(range(0, len(ids) - 1, T))
    total_nll = 0.0
    for s in starts:
        chunk = data[s : s + T + 1]
        x, y = chunk[:-1].unsqueeze(0), chunk[1:].unsqueeze(0)
        logits, _ = model(x)
        # Somme (et pas moyenne) des -ln p, pour pondérer correctement la dernière fenêtre.
        total_nll += F.cross_entropy(logits.view(-1, logits.size(-1)), y.view(-1), reduction="sum").item()
    model.train(was_training)
    return bits_per_byte(total_nll, text)
