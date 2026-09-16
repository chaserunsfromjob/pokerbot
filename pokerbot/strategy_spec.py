"""Versioned, validated strategy identity for confirmation; no placeholder models."""
from dataclasses import asdict

from .policies import EquityConfig
from .river_search import RiverConfig
from .turn_search import TurnConfig

CONFIGS = {"equity": EquityConfig, "river": RiverConfig, "turn": TurnConfig}


def parse_candidate(value):
    """Return canonical JSON specification and exact configuration instance.

    Legacy flat EquityConfig JSON and exact EquityConfig objects remain valid.
    Search policies require an explicit type and learning mode.
    """
    if type(value) is EquityConfig:
        value = asdict(value)
    if not isinstance(value, dict):
        raise ValueError("Candidate must be a strategy specification or legacy equity parameters")
    if not any(key in value for key in ("schema", "policy", "parameters", "learning")):
        try:
            config = EquityConfig(**value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid legacy equity parameters") from exc
        value = {"schema": 1, "policy": "equity", "parameters": asdict(config),
                 "learning": "learned" if config.adaptive else "off"}
    if set(value) != {"schema", "policy", "parameters", "learning"} or type(value["schema"]) is not int or value["schema"] != 1:
        raise ValueError("Unsupported strategy schema or fields")
    policy, learning = value["policy"], value["learning"]
    if not isinstance(policy, str) or policy not in CONFIGS:
        raise ValueError("Unsupported confirmation policy")
    if learning not in ("off", "learned") or not isinstance(value["parameters"], dict):
        raise ValueError("Invalid learning mode or parameters; oracle input is diagnostic only")
    try:
        config = CONFIGS[policy](**value["parameters"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {policy} parameters") from exc
    if policy == "equity":
        if type(config.samples) is not int or type(config.adaptive) is not bool:
            raise ValueError("Equity sample count and adaptive flag require integer and boolean types")
        if config.adaptive != (learning == "learned"):
            raise ValueError("Equity learning mode disagrees with adaptive configuration")
    elif learning == "learned" and config.response_model != "named":
        raise ValueError("Learned search requires the named response model")
    return {"schema": 1, "policy": policy, "parameters": asdict(config), "learning": learning}, config
