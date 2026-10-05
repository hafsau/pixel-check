"""URL policy for live mode (Hafsa's idea, refined by the council, Oct 5): PixelCheck does not rebuild banks, payment,
crypto, government, healthcare or sign-in pages from a URL, nor addresses that imitate them. A stated policy plus a
layered check — not a security guarantee (an uploaded screenshot bypasses it; the UI says so).

Layers: domain suffixes (.bank, .gov …) · curated high-risk hosts (policy_hosts.json) · lookalikes (a brand's name
off its own domain, one-character edits, punycode hosts) · raw IP hosts · login-token query parameters · after the
capture, the page title / site name. Each check returns None (allowed) or {"category", "reason"}.
"""
from __future__ import annotations

import ipaddress
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl

SUFFIXES = [  # (suffix labels, category)
    (("bank",), "banking"), (("insurance",), "banking"),
    (("gov",), "government"), (("mil",), "government"),
    (("nhs", "uk"), "healthcare"),
]
SECOND_LEVEL_GOV = {"gov", "gouv", "gob", "govt", "mil"}          # gov.uk, gouv.fr, gob.mx, govt.nz …
PUBLIC_2LD = {"co.uk", "org.uk", "ac.uk", "gov.uk", "nhs.uk", "com.au", "net.au", "gov.au", "co.nz", "govt.nz",
              "co.jp", "co.in", "com.br", "com.mx", "gob.mx", "gob.es", "gouv.fr", "com.sg", "co.za", "com.tr"}
# brands that are ordinary words: kept off the lookalike / title checks (their own domains are still refused)
GENERIC = {"discover", "ally", "wise", "cash", "chime", "square", "fidelity", "vanguard", "checkout", "gemini", "crypto",
           "ledger", "phantom", "exodus", "kraken", "regions", "anthem", "affirm", "citizensbank"}
TOKEN_PARAM = re.compile(r"^(?:.*[_-])?(?:token|key|sig|signature|code|session|sessionid|auth|otp|password|secret)$",
                         re.I)
WORDS = [(re.compile(p, re.I), c) for p, c in [
    (r"\bonline banking\b|\bbank account\b|\bbanking (?:login|sign[ -]?in)\b", "banking"),
    (r"\bseed phrase\b|\bconnect (?:your )?wallet\b|\bcrypto wallet\b", "crypto"),
    (r"\bpatient portal\b|\bmedical records?\b", "healthcare"),
]]


@lru_cache(maxsize=1)
def _hosts() -> dict[str, str]:
    data = json.loads((Path(__file__).with_name("policy_hosts.json")).read_text())
    return {h.lower(): cat for cat, hosts in data.items() for h in hosts}


@lru_cache(maxsize=1)
def _brands() -> dict[str, str]:
    """Brand label → category, from the curated hosts' registrable names (paypal, chase, coinbase …)."""
    out = {}
    for h, cat in _hosts().items():
        if cat == "sign-in":
            continue
        label = _registrable(h).split(".")[0]
        if len(label) >= 4 and label not in GENERIC:
            out[label] = cat
    return out


def _registrable(host: str) -> str:
    labels = host.lower().strip(".").split(".")
    n = 3 if len(labels) >= 3 and ".".join(labels[-2:]) in PUBLIC_2LD else 2
    return ".".join(labels[-n:])


def _edit1(a: str, b: str) -> bool:
    """Exactly one insertion, deletion or substitution apart."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    s, l = (a, b) if len(a) < len(b) else (b, a)
    return any(l[:i] + l[i + 1:] == s for i in range(len(l)))


def check_host(host: str) -> dict | None:
    host = (host or "").lower().strip(".")
    try:
        ipaddress.ip_address(host)
        return {"category": "ip-address", "reason": "addresses must be domain names, not IP addresses"}
    except ValueError:
        pass
    labels = host.split(".")
    for suf, cat in SUFFIXES:
        if tuple(labels[-len(suf):]) == suf:
            return {"category": cat, "reason": f".{'.'.join(suf)} domains are not rebuilt"}
    if len(labels) >= 3 and labels[-2] in SECOND_LEVEL_GOV or labels[0] in SECOND_LEVEL_GOV and len(labels) == 2 \
            and labels[1] in ("uk", "fr", "es", "mx", "au", "nz"):
        return {"category": "government", "reason": "government domains are not rebuilt"}
    for h, cat in _hosts().items():
        if host == h or host.endswith("." + h):
            return {"category": cat, "reason": f"{h} is a {cat} site"}
    if any(l.startswith("xn--") for l in labels):
        return {"category": "lookalike", "reason": "internationalised (punycode) addresses can imitate other sites"}
    reg = _registrable(host)
    reg_label = reg.split(".")[0]
    tokens = set(re.split(r"[.-]", host))
    for brand, cat in _brands().items():
        if brand in tokens and reg_label != brand:
            return {"category": "lookalike", "reason": f"the address uses the name '{brand}' outside its own domain"}
        if len(brand) >= 5 and _edit1(reg_label, brand):
            return {"category": "lookalike", "reason": f"the address is one character away from '{brand}'"}
    return None


def check_query(query: str) -> dict | None:
    for k, _ in parse_qsl(query or "", keep_blank_values=True):
        if TOKEN_PARAM.match(k):
            return {"category": "private link", "reason": f"links carrying '{k}' may open a signed-in page"}
    return None


def check_page(title: str, site_name: str = "") -> dict | None:
    """After the capture: the page's own title / og:site_name naming a high-risk brand or service."""
    text = f"{title or ''} {site_name or ''}"
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    for brand, cat in _brands().items():
        if brand in words:
            return {"category": cat, "reason": f"the page presents itself as {brand}"}
    for rx, cat in WORDS:
        if rx.search(text):
            return {"category": cat, "reason": "the page presents itself as a " + cat + " service"}
    return None


def refusal(r: dict) -> str:
    cat = r["category"]
    what = {"lookalike": "addresses that imitate well-known sites", "ip-address": "raw IP addresses",
            "private link": "private or signed-in links"}.get(cat, f"{cat} pages")
    return f"PixelCheck does not rebuild {what} from a URL — if it is your own page, upload your design frames instead."
