"""Check minigpt.value.Value gradients against hand computations and PyTorch."""

import math

import pytest
import torch

from minigpt.value import Value

TOL = 1e-6


def test_forward_values():
    a, b = Value(2.0), Value(-3.0)
    assert (a + b).data == -1.0
    assert (a * b).data == -6.0
    assert (a - b).data == 5.0
    assert (a / b).data == pytest.approx(-2.0 / 3.0)
    assert (a**3).data == 8.0
    assert (-a).data == -2.0
    assert b.relu().data == 0.0
    assert a.tanh().data == pytest.approx(math.tanh(2.0))
    assert a.exp().data == pytest.approx(math.exp(2.0))


def test_mixed_with_plain_numbers():
    a = Value(2.0)
    assert (a + 1).data == 3.0
    assert (1 + a).data == 3.0
    assert (a * 3).data == 6.0
    assert (3 * a).data == 6.0
    assert (1 - a).data == -1.0
    assert (1 / a).data == 0.5


def test_hand_example():
    # z = x*y + x  ->  dz/dx = y + 1 = 4, dz/dy = x = 2
    x, y = Value(2.0), Value(3.0)
    z = x * y + x
    z.backward()
    assert z.data == 8.0
    assert z.grad == 1.0
    assert x.grad == 4.0
    assert y.grad == 2.0


def test_same_node_used_twice():
    # b = a + a  ->  db/da = 2 (fails if grads are assigned instead of accumulated)
    a = Value(3.0)
    b = a + a
    b.backward()
    assert a.grad == 2.0


def test_order_matters_deep_graph():
    # d is reached through two paths of different lengths: needs a topological order
    a = Value(-2.0)
    b = Value(3.0)
    d = a * b
    e = a + b
    f = d * e
    f.backward()
    # f = (a*b)*(a+b) -> df/da = b*(a+b) + a*b = 3*1 + (-6) = -3, df/db = a*(a+b) + a*b = -2 + (-6) = -8
    assert a.grad == -3.0
    assert b.grad == -8.0


def test_against_pytorch_expression():
    # Same expression built twice: with Value, then with torch (float64), grads must match.
    a, b = Value(-4.0), Value(2.0)
    c = a + b
    d = a * b + b**3
    c = c + c + 1
    c = c + 1 + c + (-a)
    d = d + d * 2 + (b + a).relu()
    d = d + 3 * d + (b - a).relu()
    e = c - d
    f = e**2
    g = f / 2.0
    g = g + 10.0 / f
    g.backward()

    at = torch.tensor(-4.0, dtype=torch.double, requires_grad=True)
    bt = torch.tensor(2.0, dtype=torch.double, requires_grad=True)
    ct = at + bt
    dt = at * bt + bt**3
    ct = ct + ct + 1
    ct = ct + 1 + ct + (-at)
    dt = dt + dt * 2 + (bt + at).relu()
    dt = dt + 3 * dt + (bt - at).relu()
    et = ct - dt
    ft = et**2
    gt = ft / 2.0
    gt = gt + 10.0 / ft
    gt.backward()

    assert g.data == pytest.approx(gt.item(), abs=TOL)
    assert a.grad == pytest.approx(at.grad.item(), abs=TOL)
    assert b.grad == pytest.approx(bt.grad.item(), abs=TOL)


def test_against_pytorch_neuron():
    # One tanh neuron: out = tanh(w1*x1 + w2*x2 + b), then a squared-error-like loss with exp.
    xs, ws, bias = [2.0, 0.5], [-3.0, 1.0], 6.8813735870195432

    x = [Value(v) for v in xs]
    w = [Value(v) for v in ws]
    b = Value(bias)
    out = (x[0] * w[0] + x[1] * w[1] + b).tanh()
    loss = (out - 0.3) ** 2 + (out * 0.5).exp()
    loss.backward()

    xt = [torch.tensor(v, dtype=torch.double, requires_grad=True) for v in xs]
    wt = [torch.tensor(v, dtype=torch.double, requires_grad=True) for v in ws]
    bt = torch.tensor(bias, dtype=torch.double, requires_grad=True)
    outt = (xt[0] * wt[0] + xt[1] * wt[1] + bt).tanh()
    losst = (outt - 0.3) ** 2 + (outt * 0.5).exp()
    losst.backward()

    assert loss.data == pytest.approx(losst.item(), abs=TOL)
    for v, t in zip(x + w + [b], xt + wt + [bt]):
        assert v.grad == pytest.approx(t.grad.item(), abs=TOL)


def test_relu_gradient_is_zero_when_negative():
    a = Value(-1.5)
    a.relu().backward()
    assert a.grad == 0.0
