"""Session-scoped public observations, separate from policy implementations."""
from collections import defaultdict
from dataclasses import asdict
import json
import sqlite3


class Profiles:
    def __init__(self, path=":memory:", session="trial"):
        self.session = session
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS hands (session TEXT, hand TEXT, events TEXT, PRIMARY KEY(session,hand))")
        self.counts = defaultdict(lambda: [0, 0])
        for (raw,) in self.db.execute("SELECT events FROM hands WHERE session=? ORDER BY rowid", (session,)):
            self._count(json.loads(raw))

    def _count(self, events):
        for e in events:
            if e["facing_bet"]:
                row = self.counts[e["name"]]
                row[0] += 1
                row[1] += e["kind"] == "fold"

    def record(self, hand_id, events):
        rows = [asdict(e) for e in events]
        with self.db:
            result = self.db.execute("INSERT OR IGNORE INTO hands VALUES (?,?,?)",
                                     (self.session, str(hand_id), json.dumps(rows)))
        if result.rowcount:
            self._count(rows)

    def view(self):
        # Independent copies; no cards, future events or access to the database.
        return {name: {"facing_bet": n, "folds": f, "fold_rate": (f + 2) / (n + 5)}
                for name, (n, f) in self.counts.items()}

    def close(self):
        self.db.close()
