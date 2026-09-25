"""Strict JSON parsing shared by evaluation and promotion entrypoints."""

from __future__ import annotations

import json
import math


def loads_strict(text: str) -> object:
    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON value: {value}")

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"non-finite JSON number: {value}")
        return parsed

    def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
        payload: dict = {}
        for key, value in pairs:
            if key in payload:
                raise ValueError(f"duplicate JSON key: {key}")
            payload[key] = value
        return payload

    return json.loads(text, parse_constant=reject_constant, parse_float=finite_float, object_pairs_hook=unique_pairs)
