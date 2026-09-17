import time, random
from phevaluator import evaluate_cards
random.seed(1)
ranks="23456789TJQKA"; suits="cdhs"
deck=[r+s for r in ranks for s in suits]
N=200000
hands=[random.sample(deck,7) for _ in range(N)]
t=time.perf_counter()
for h in hands: evaluate_cards(*h)
dt=time.perf_counter()-t
print(f"phevaluator 7-card (string cards): {N/dt:,.0f} hands/s ({dt:.2f}s)")
ints=[[deck.index(c) for c in h] for h in hands]
t=time.perf_counter()
for h in ints: evaluate_cards(*h)
dt=time.perf_counter()-t
print(f"phevaluator 7-card (int cards): {N/dt:,.0f} hands/s ({dt:.2f}s)")
