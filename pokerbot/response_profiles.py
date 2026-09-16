"""Named, session-scoped public action counts; no cards or private policy data."""
from collections import defaultdict
from copy import deepcopy
import json
import math
import sqlite3

KINDS = ("fold", "passive", "raise")


def context_key(street, facing_bet, raise_available):
    if type(street) is not int or street not in range(4):
        raise ValueError("Invalid betting street")
    if type(facing_bet) is not bool or type(raise_available) is not bool:
        raise ValueError("Context flags must be booleans")
    return f"{street}:{int(facing_bet)}:{int(raise_available)}"


def public_response(obs, decision):
    if not obs.legal.contains(decision.action):
        raise ValueError("Cannot record an illegal action")
    return {"name": obs.players[obs.actor].name, "street": obs.street,
            "facing_bet": bool(obs.legal.call_cost),
            "raise_available": obs.legal.min_raise_to is not None,
            "action": "fold" if decision.action == 0 else "passive" if decision.action == 1 else "raise"}


class ResponseProfiles:
    def __init__(self, path=":memory:", session="trial", *, half_life=None):
        if half_life is not None and (type(half_life) not in (int, float)
                                     or not math.isfinite(half_life) or half_life <= 0):
            raise ValueError("Half-life must be a finite positive number or None")
        self.session = session
        self.config = {"schema": 1, "half_life": None if half_life is None else float(half_life)}
        self.decay = None if half_life is None else 2 ** (-1 / half_life)
        self.db = sqlite3.connect(path)
        self.counts = defaultdict(dict)
        try:
            with self.db:
                self.db.execute("CREATE TABLE IF NOT EXISTS response_hands (session TEXT, hand TEXT, observations TEXT, PRIMARY KEY(session,hand))")
                self.db.execute("CREATE TABLE IF NOT EXISTS response_settings (session TEXT PRIMARY KEY, config TEXT)")
                saved = self.db.execute("SELECT config FROM response_settings WHERE session=?", (session,)).fetchone()
                legacy = self.db.execute("SELECT 1 FROM response_hands WHERE session=? LIMIT 1", (session,)).fetchone()
                if saved is None and legacy and half_life is not None:
                    raise ValueError("Legacy profiles use raw counts; choose a new session for discounting")
                self.db.execute("INSERT OR IGNORE INTO response_settings VALUES (?,?)", (session, json.dumps(self.config)))
                saved = self.db.execute("SELECT config FROM response_settings WHERE session=?", (session,)).fetchone()
                if json.loads(saved[0]) != self.config:
                    raise ValueError("Cannot reopen a session with changed response-model settings")
            for (raw,) in self.db.execute("SELECT observations FROM response_hands WHERE session=? ORDER BY rowid", (session,)):
                self._count(json.loads(raw))
        except Exception:
            self.db.close()
            raise

    def _count(self, rows):
        for row in rows:
            key = context_key(row["street"], row["facing_bet"], row["raise_available"])
            player = self.counts[row["name"]]
            if self.decay is not None:
                # Age only this player's evidence, once per observed action,
                # including evidence in other legal/street contexts.
                for counts in player.values():
                    for i in range(3):
                        counts[i] *= self.decay
            counts = player.setdefault(key, [0, 0, 0])
            counts[KINDS.index(row["action"])] += 1

    def record(self, hand_id, rows):
        # Validate before committing; an invalid hand cannot poison later reloads.
        clean = []
        for row in rows:
            if not isinstance(row["name"], str) or not row["name"]:
                raise ValueError("Player name must be a nonempty string")
            context_key(row["street"], row["facing_bet"], row["raise_available"])
            action = row["action"]
            if (action not in KINDS or (action == "fold" and not row["facing_bet"])
                    or (action == "raise" and not row["raise_available"])):
                raise ValueError("Action conflicts with recorded legal context")
            clean.append({key: row[key] for key in ("name", "street", "facing_bet", "raise_available", "action")})
        with self.db:
            result = self.db.execute("INSERT OR IGNORE INTO response_hands VALUES (?,?,?)",
                                     (self.session, str(hand_id), json.dumps(clean)))
        if result.rowcount:
            self._count(clean)

    def view(self):
        return {name: {"responses": deepcopy(counts)} for name, counts in self.counts.items()}

    def close(self):
        self.db.close()
