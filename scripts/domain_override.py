"""Single source of truth for Magnetio domain overrides.

Used by scripts/magnetio-patch.py at build time and by the auto-healer during
candidate validation, so the two can never drift apart.
"""
import re


def _pattern(provider_id):
    return re.compile(
        r"((?:'" + re.escape(provider_id) + r"'|" + re.escape(provider_id) + r"):\s*\[)([^\]]*)(\])"
    )


def has_key(text, provider_id):
    return bool(_pattern(provider_id).search(text))


def apply(text, overrides):
    """Replace PROVIDER_DOMAINS arrays. Raises if an anchor is missing."""
    for provider_id, urls in overrides.items():
        clean = [u for u in urls if isinstance(u, str) and u.startswith("https://")]
        if not clean:
            continue
        rendered = "\n".join(f"    '{u}'," for u in clean)
        replacement = lambda m: m.group(1) + "\n" + rendered + "\n  " + m.group(3)
        text, count = _pattern(provider_id).subn(replacement, text, count=1)
        if count != 1:
            raise ValueError(f"domain override anchor missing for {provider_id!r}")
    return text
