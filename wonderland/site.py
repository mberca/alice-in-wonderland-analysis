"""Embed computed evidence in a self-contained browser story."""

import json
from pathlib import Path


def script_json(value):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def render_story(result, evidence, template):
    template = Path(template).read_text(encoding="utf-8")
    if template.count("__WONDERLAND_DATA__") != 1:
        raise ValueError("The story template must contain exactly one data placeholder.")
    return template.replace("__WONDERLAND_DATA__", script_json({"analysis": result, "evidence": evidence}))
