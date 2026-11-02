"""Turn bank / UPI / card narrations into a clean merchant name.

UPI/DR/402918374651/SWIGGY/YESB/swiggy@ybl/Payment  ->  Swiggy
NEFT-HDFCN52026110112-ACME TECH PVT LTD-SALARY       ->  Acme Tech (Salary)
"""

import re

_SEGMENT_SPLIT = re.compile(r"[/|\\-]")

_STOPWORDS = frozenset(
    [
        "UPI",
        "DR",
        "CR",
        "NEFT",
        "IMPS",
        "RTGS",
        "POS",
        "ACH",
        "ECS",
        "NACH",
        "SI",
        "MB",
        "IB",
        "BIL",
        "BILLPAY",
        "ONL",
        "INB",
        "MMT",
        "D",
        "C",
        "P2A",
        "P2M",
        "P2P",
        "TO",
        "FROM",
        "BY",
        "VIA",
        "TRANSFER",
        "TRF",
        "TXN",
        "TRAN",
        "REF",
        "NO",
        "PAYMENT",
        "PAYMENTS",
        "PAID",
        "PAY",
        "SENT",
        "RECEIVED",
        "COLLECT",
        "REQUEST",
        "INTENT",
        "NA",
        "NULL",
        "OTHERS",
        "UPIINTENT",
        "PHONE",
        "MOBILE",
        "APP",
        "USING",
    ]
)

# 4-letter bank prefixes that show up as standalone narration tokens.
_BANK_CODES = frozenset(
    [
        "YESB",
        "HDFC",
        "ICIC",
        "SBIN",
        "UTIB",
        "KKBK",
        "PYTM",
        "AXIS",
        "BARB",
        "PUNB",
        "CNRB",
        "UBIN",
        "IDIB",
        "IOBA",
        "MAHB",
        "INDB",
        "IDFB",
        "FDRL",
        "KARB",
        "CBIN",
        "CIUB",
        "AIRP",
        "JIOP",
        "ESFB",
        "AUBL",
        "RATN",
        "DBSS",
        "SCBL",
        "CITI",
        "HSBC",
        "BKID",
        "HDFCBANK",
        "ICICIBANK",
        "SBI",
        "AXISBANK",
        "KOTAK",
    ]
)

_PURPOSE_TAGS = {"SALARY": "Salary", "SAL": "Salary", "STIPEND": "Stipend", "PAYROLL": "Salary"}

_COMPANY_SUFFIXES = frozenset(
    {"PVT", "PRIVATE", "LTD", "LTD.", "LIMITED", "LLP", "INC", "CORP", "CO", "PVTLTD"}
)

_TRAILING_NOISE = frozenset({"IN", "IND", "INDIA", "BANGALORE", "BENGALURU", "MUMBAI", "DELHI"})

_ACRONYMS = frozenset(
    [
        "KFC",
        "PVR",
        "IRCTC",
        "BMTC",
        "BWSSB",
        "BESCOM",
        "HPCL",
        "BPCL",
        "ACT",
        "BSNL",
        "LIC",
        "SBI",
        "HDFC",
        "ICICI",
        "ATM",
        "IOCL",
        "DMART",
    ]
)

# Lowercase phrase -> canonical name. Longer phrases are tried first.
_ALIASES: dict[str, str] = {
    "swiggy instamart": "Swiggy Instamart",
    "instamart": "Swiggy Instamart",
    "swiggy": "Swiggy",
    "zomato": "Zomato",
    "blinkit": "Blinkit",
    "zepto": "Zepto",
    "bigbasket": "BigBasket",
    "amazon pay": "Amazon",
    "amazon": "Amazon",
    "amzn": "Amazon",
    "flipkart": "Flipkart",
    "myntra": "Myntra",
    "uber": "Uber",
    "rapido": "Rapido",
    "ola cabs": "Ola",
    "ani technologies": "Ola",
    "netflix": "Netflix",
    "spotify": "Spotify",
    "dominos": "Domino's",
    "jubilant foodworks": "Domino's",
    "mcdonald": "McDonald's",
    "starbucks": "Starbucks",
    "bookmyshow": "BookMyShow",
    "big tree": "BookMyShow",
    "irctc": "IRCTC",
    "airtel": "Airtel",
    "jiomart": "JioMart",
    "jio mart": "JioMart",
    "reliance jio": "Jio",
    "jio": "Jio",
    "phonepe": "PhonePe",
    "google play": "Google Play",
    "apple.com": "Apple",
}
_ALIAS_PATTERNS = [
    (re.compile(rf"\b{re.escape(phrase)}\b"), name)
    for phrase, name in sorted(_ALIASES.items(), key=lambda kv: -len(kv[0]))
]

_IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_LONG_DIGITS = re.compile(r"\d{5,}")
_MASKED = re.compile(r"[X*]{3,}", re.IGNORECASE)
_HAS_DIGIT = re.compile(r"\d")


def _is_noise(word: str) -> bool:
    up = word.upper().strip(".,:;#*()[]")
    if not up:
        return True
    if up in _STOPWORDS or up in _BANK_CODES:
        return True
    if "@" in word:  # VPA
        return True
    if _IFSC.match(up) or _LONG_DIGITS.search(up) or _MASKED.search(up):
        return True
    # Reference-like tokens: mixed letters + digits, e.g. P400XXXX, HDFCN5202...
    digits = sum(ch.isdigit() for ch in up)
    return digits >= 3 and len(up) >= 6 or up.isdigit()


def _strip_company_suffixes(words: list[str]) -> list[str]:
    while words and words[-1].upper() in _COMPANY_SUFFIXES | _TRAILING_NOISE:
        words = words[:-1]
    return words


def _title(words: list[str]) -> str:
    out = []
    for w in words:
        up = w.upper()
        out.append(up if up in _ACRONYMS else w[:1].upper() + w[1:].lower())
    return " ".join(out)


def _alias(text: str) -> str | None:
    low = text.lower()
    for pattern, name in _ALIAS_PATTERNS:
        if pattern.search(low):
            return name
    return None


def extract_merchant(raw: str) -> str:
    text = " ".join((raw or "").split())
    if not text:
        return ""

    purpose: str | None = None
    payee: str | None = None
    vpa_handle: str | None = None

    for segment in _SEGMENT_SPLIT.split(text):
        words = segment.split()
        if not words:
            continue
        for w in words:
            if "@" in w and vpa_handle is None:
                vpa_handle = w.split("@", 1)[0]
        kept = [w for w in words if not _is_noise(w)]
        if not kept:
            continue
        tag = _PURPOSE_TAGS.get(kept[0].upper())
        if tag:
            purpose = purpose or tag
            continue
        kept = _strip_company_suffixes(kept)
        if kept and payee is None:
            payee = " ".join(kept)

    candidate = payee or (vpa_handle or "")
    # Alias only the payee when we have one: a VPA domain like "@jio" must not rename a person.
    name = _alias(candidate) if candidate else _alias(text)
    if not name:
        cleaned = re.sub(r"[^A-Za-z0-9&.' ]", " ", candidate)
        name = _title(cleaned.split()) if cleaned.strip() else ""
    if not name:
        return ""
    if purpose:
        name = f"{name} ({purpose})"
    return name[:160]
