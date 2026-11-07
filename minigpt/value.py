"""Mini autograd : un scalaire qui se souvient de la façon dont il a été calculé.

Chaque opération construit une nouvelle Value et enregistre (1) ses parents et
(2) une petite fonction `_backward` qui renvoie le gradient de la sortie vers
ces parents, multiplié par la dérivée locale (règle de la chaîne).
`backward()` appelle ces fonctions de la sortie vers les entrées.
"""

import math


class Value:
    def __init__(self, data, parents=()):
        self.data = float(data)
        self.grad = 0.0
        self._parents = parents
        self._backward = lambda: None  # une feuille n'a rien à propager

    @staticmethod
    def _wrap(x):
        # permet d'écrire a + 1 : le nombre devient une Value
        return x if isinstance(x, Value) else Value(x)

    # --- opérations de base : out._backward fait parent.grad += dérivée_locale * out.grad ---
    # `+=` (et pas `=`) : un nœud utilisé plusieurs fois reçoit une contribution par usage.

    def __add__(self, other):
        other = self._wrap(other)
        out = Value(self.data + other.data, (self, other))

        def _backward():
            self.grad += out.grad   # d(a+b)/da = 1
            other.grad += out.grad  # d(a+b)/db = 1

        out._backward = _backward
        return out

    def __mul__(self, other):
        other = self._wrap(other)
        out = Value(self.data * other.data, (self, other))

        def _backward():
            self.grad += other.data * out.grad  # d(a*b)/da = b
            other.grad += self.data * out.grad  # d(a*b)/db = a

        out._backward = _backward
        return out

    def __pow__(self, n):
        assert isinstance(n, (int, float)), "l'exposant doit être un nombre simple"
        out = Value(self.data**n, (self,))

        def _backward():
            self.grad += n * self.data ** (n - 1) * out.grad  # d(a^n)/da = n a^(n-1)

        out._backward = _backward
        return out

    def relu(self):
        out = Value(max(0.0, self.data), (self,))

        def _backward():
            self.grad += (out.data > 0) * out.grad  # 1 si actif, 0 sinon

        out._backward = _backward
        return out

    def tanh(self):
        t = math.tanh(self.data)
        out = Value(t, (self,))

        def _backward():
            self.grad += (1 - t**2) * out.grad  # d tanh(a)/da = 1 - tanh²

        out._backward = _backward
        return out

    def exp(self):
        e = math.exp(self.data)
        out = Value(e, (self,))

        def _backward():
            self.grad += e * out.grad  # d exp(a)/da = exp(a)

        out._backward = _backward
        return out

    # --- opérations dérivées : construites avec celles de base, donc gradients gratuits ---

    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + (-self._wrap(other))

    def __truediv__(self, other):
        return self * self._wrap(other) ** -1

    def __radd__(self, other):  # 1 + a
        return self + other

    def __rmul__(self, other):  # 3 * a
        return self * other

    def __rsub__(self, other):  # 1 - a
        return self._wrap(other) + (-self)

    def __rtruediv__(self, other):  # 1 / a
        return self._wrap(other) * self**-1

    # --- rétropropagation ---

    def backward(self):
        # Ordre topologique : chaque nœud vient après ses parents.
        topo, visited = [], set()

        def build(v):
            if v not in visited:
                visited.add(v)
                for p in v._parents:
                    build(p)
                topo.append(v)

        build(self)

        self.grad = 1.0  # d(self)/d(self) = 1 : la graine de la règle de la chaîne
        for v in reversed(topo):  # sorties d'abord : le grad d'un nœud est complet avant qu'il le propage
            v._backward()
