"""Sanitized one-request JSON process boundary for locally supplied policies.

This is a trusted executable interface, not an OS security sandbox. The host
passes no simulator state; a malicious process with filesystem access could
still read privileged replay logs. Use OS isolation for untrusted executables.
"""
from dataclasses import asdict
import json
import subprocess

from .engine import Decision


CANDIDATES = {
    "noregrets": {
        "url": "https://github.com/conorarmstrong/noregrets",
        "status": "blocked: local trained blueprint and native protocol bridge required",
        "supported_seats": [2, 3, 4, 5, 6],
        "risk": "7–9 seats unsupported upstream; source availability is not a strength result",
    },
    "dickreuter": {
        "url": "https://github.com/dickreuter/Poker",
        "commit": "cae3a108b6cbf22ed8ef90bc0e70f790346289a4",
        "status": "blocked: isolated local strategy config and policy bridge required",
        "risk": "Upstream tie-equity error: board royal flush returns 1.0 instead of 1/N; apply and verify research patch before using",
    },
}


class ProcessPolicy:
    def __init__(self, command, timeout_seconds=10):
        if not command or isinstance(command, str):
            raise ValueError("Supply argv, not a shell command")
        self.command = list(command)
        self.timeout = timeout_seconds

    def decide(self, obs, profiles, rng):
        request = {"protocol": 1, "observation": asdict(obs), "profiles": profiles,
                   "seed": rng.getrandbits(64), "action_units": "total_hand_raise_to"}
        proc = subprocess.run(self.command, input=json.dumps(request), text=True,
                              capture_output=True, timeout=self.timeout, check=True)
        raw = json.loads(proc.stdout)
        result = Decision(raw["action"], raw.get("diagnostics", {}))
        if not obs.legal.contains(result.action):
            raise ValueError("External policy returned an illegal action")
        return result
