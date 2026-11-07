"""Mini autograd: a scalar that remembers how it was computed.

Each operation builds a new Value and records (1) its parents and (2) a small
function `_backward` that pushes the output's gradient back to those parents,
multiplied by the local derivative (chain rule). `backward()` calls these
functions from the output back to the inputs.
"""

import math


class Value:
    def __init__(self, data, parents=()):
        self.data = float(data)
        self.grad = 0.0
        self._parents = parents
        self._backward = lambda: None  # leaves have nothing to propagate

    @staticmethod
    def _wrap(x):
        return x if isinstance(x, Value) else Value(x)

    # --- core ops: out._backward does parent.grad += local_derivative * out.grad ---
    # `+=` (not `=`): a node used several times receives one contribution per use.

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
        assert isinstance(n, (int, float)), "exponent must be a plain number"
        out = Value(self.data**n, (self,))

        def _backward():
            self.grad += n * self.data ** (n - 1) * out.grad  # d(a^n)/da = n a^(n-1)

        out._backward = _backward
        return out

    def relu(self):
        out = Value(max(0.0, self.data), (self,))

        def _backward():
            self.grad += (out.data > 0) * out.grad  # 1 if active, else 0

        out._backward = _backward
        return out

    def tanh(self):
        t = math.tanh(self.data)
        out = Value(t, (self,))

        def _backward():
            self.grad += (1 - t**2) * out.grad  # d tanh(a)/da = 1 - tanh^2

        out._backward = _backward
        return out

    def exp(self):
        e = math.exp(self.data)
        out = Value(e, (self,))

        def _backward():
            self.grad += e * out.grad  # d exp(a)/da = exp(a)

        out._backward = _backward
        return out

    # --- derived ops: built from the core ones, so they get gradients for free ---

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

    # --- backprop ---

    def backward(self):
        # Topological order: every node comes after its parents.
        topo, visited = [], set()

        def build(v):
            if v not in visited:
                visited.add(v)
                for p in v._parents:
                    build(p)
                topo.append(v)

        build(self)

        self.grad = 1.0  # d(self)/d(self) = 1: the seed of the chain rule
        for v in reversed(topo):  # outputs first, so a node's grad is complete before it propagates
            v._backward()
