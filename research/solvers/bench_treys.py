import time, random
from treys import Card, Deck, Evaluator
ev = Evaluator()
N = 200000
hands = []
for _ in range(N):
    d = Deck(); cards = d.draw(7)
    hands.append((cards[:2], cards[2:]))
t = time.perf_counter()
for h, b in hands:
    ev.evaluate(h, b)
dt = time.perf_counter() - t
print(f"treys 7-card evaluate: {N/dt:,.0f} hands/s ({dt:.2f}s for {N})")
