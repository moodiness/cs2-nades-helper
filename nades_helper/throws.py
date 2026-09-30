"""Heuristics reading throw instructions from free-text lineup descriptions."""

from __future__ import annotations

import re

JUMP_THROW_PATTERN = re.compile(r"\b(?:j[\s._-]*t|jump(?:ing)?[\s_-]*throws?)\b", re.IGNORECASE)
THROW_ACTION_PATTERN = re.compile(JUMP_THROW_PATTERN.pattern + r"|\bthrows?\b", re.IGNORECASE)
SETUP_PATTERN = re.compile(r"\([^)]*\)|\b(?:crouched|standing)\s+line[- ]up\b")
ACTION_PATTERN = re.compile(
    r"\b(?:stand(?:ing)?|crouch(?:ed|ing)?|duck(?:ed|ing)?|run(?:ning)?|m[12])\b"
)


def is_jump_throw(desc: str) -> bool:
    """Recognize ``jt``, ``J.T.``, ``JumpThrow``, ``jump throw``, ``jump-throw``..."""
    return JUMP_THROW_PATTERN.search(desc) is not None


def throw_settings(desc: str) -> tuple[str, str]:
    """Infer ``(stance, throw)`` from the instruction that performs the throw.

    Setup postures (``crouched line-up``, text in parentheses) and hints written after the
    throw are ignored. Defaults: ``standing`` and ``primary`` (M1).
    """
    description = SETUP_PATTERN.sub(" ", desc.lower())
    action = THROW_ACTION_PATTERN.search(description)
    if action is not None:
        description = description[: action.start()]

    stance = "standing"
    primary = False
    secondary = False
    for match in ACTION_PATTERN.finditer(description):
        word = match.group()
        if word.startswith(("crouch", "duck")):
            stance = "crouched"
        elif word.startswith(("stand", "run")):
            stance = "standing"
        elif word == "m1":
            primary = True
        elif word == "m2":
            secondary = True

    throw = "both" if primary and secondary else "secondary" if secondary else "primary"
    return stance, throw
