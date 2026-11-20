"""
pipeline/config.py — config loader for the companion pipeline.

PRODUCTION NOTE: freemarketresearcher.com's real RagSystem reads its own
config module (RagSystem/crawler/config.py), wired to a real Qdrant
instance and nomic-embed-text:v1.5 via Ollama. This loader is the
Chapter 1 Lab's simplified stand-in: one YAML file (pipeline/config.yaml,
copied from pipeline/config.example.yaml), loaded with PyYAML if it's
installed, or with a small hand-rolled YAML-subset parser if it isn't --
so the Lab still runs on a bare `python3` with zero pip installs.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "pipeline" / "config.yaml"
EXAMPLE_CONFIG_PATH = REPO_ROOT / "pipeline" / "config.example.yaml"


def _strip_comment(line: str) -> str:
    """Remove a trailing ' # comment', but not a value that's a quoted
    string containing '#'. Good enough for this repo's own config files."""
    if line.strip().startswith("#"):
        return ""
    # only strip "#" that's preceded by whitespace and not inside quotes
    out = []
    in_quote = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            in_quote = not in_quote
        if ch == "#" and not in_quote and i > 0 and line[i - 1] == " ":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def _minimal_yaml_load(text: str) -> dict:
    """
    Tiny YAML-subset parser: nested maps, scalars, and '|' block scalars,
    2-space indents, '#' comments. This is NOT a general YAML parser --
    it only needs to understand this repo's own config.example.yaml
    shape. Used only when PyYAML isn't importable, so the Lab has no
    required third-party dependency.
    """
    lines = text.split("\n")
    root: dict = {}
    stack = [(-1, root)]
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        if not raw.strip() or raw.strip().startswith("#"):
            i += 1
            continue
        line = _strip_comment(raw)
        if not line.strip():
            i += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            i += 1
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()

        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]

        if value == "|":
            # Block scalar: collect following more-indented lines verbatim.
            j = i + 1
            block = []
            base_indent = None
            while j < n:
                l2 = lines[j]
                if l2.strip() == "":
                    block.append("")
                    j += 1
                    continue
                ind2 = len(l2) - len(l2.lstrip(" "))
                if ind2 <= indent:
                    break
                if base_indent is None:
                    base_indent = ind2
                block.append(l2[base_indent:] if len(l2) >= base_indent else l2.strip())
                j += 1
            parent[key] = "\n".join(block).rstrip("\n") + "\n"
            i = j
            continue

        if value == "":
            # Nested map starts on the following more-indented lines.
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
            i += 1
            continue

        parent[key] = _coerce_scalar(value)
        i += 1
    return root


def _coerce_scalar(value: str):
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if len(value) >= 2 and value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value.lower() in ("null", "~", "none"):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def load_config(path=None) -> dict:
    """Load pipeline config. Falls back from config.yaml to
    config.example.yaml so the Lab works on a totally fresh checkout."""
    if path:
        cfg_path = Path(path)
    elif DEFAULT_CONFIG_PATH.exists():
        cfg_path = DEFAULT_CONFIG_PATH
    else:
        cfg_path = EXAMPLE_CONFIG_PATH

    text = cfg_path.read_text(encoding="utf-8")
    try:
        import yaml  # PyYAML, if installed
        cfg = yaml.safe_load(text)
    except ImportError:
        cfg = _minimal_yaml_load(text)

    if not isinstance(cfg, dict):
        raise ValueError(f"config at {cfg_path} did not parse to a mapping")
    return cfg
