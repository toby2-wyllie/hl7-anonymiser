"""
hl7_anonymise.py
----------------
Interactive NHS HL7 v2.x patient data anonymiser.

Just run:  python hl7_anonymise.py
The tool will guide you through everything with menus.

No flags, no configuration, no third-party dependencies.
"""

import re
import sys
import hashlib
import random
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Terminal colour helpers (graceful fallback if colours unsupported)
# ─────────────────────────────────────────────────────────────────────────────

def _supports_colour():
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOUR = _supports_colour()

def _c(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOUR else text

def green(t):   return _c(t, "32")
def yellow(t):  return _c(t, "33")
def cyan(t):    return _c(t, "36")
def bold(t):    return _c(t, "1")
def red(t):     return _c(t, "31")
def dim(t):     return _c(t, "2")


# ─────────────────────────────────────────────────────────────────────────────
# PID field map
# ─────────────────────────────────────────────────────────────────────────────

PID_SENSITIVE_FIELDS = {
    2:  "Patient ID (external)",
    3:  "Patient Identifier List (NHS Number)",
    4:  "Alternate Patient ID",
    5:  "Patient Name",
    6:  "Mother's Maiden Name",
    7:  "Date/Time of Birth",
    8:  "Administrative Sex",
    9:  "Patient Alias",
    10: "Race",
    11: "Patient Address",
    12: "County Code",
    13: "Phone Number (Home)",
    14: "Phone Number (Business)",
    15: "Primary Language",
    16: "Marital Status",
    17: "Religion",
    18: "Patient Account Number",
    19: "National ID / SSN",
    20: "Driver's Licence Number",
    21: "Mother's Identifier",
    22: "Ethnic Group",
    23: "Birth Place",
    24: "Multiple Birth Indicator",
    25: "Birth Order",
    26: "Citizenship",
    27: "Veterans Military Status",
    28: "Nationality",
    29: "Patient Death Date/Time",
    30: "Patient Death Indicator",
}

KEEP_FIELDS = {1}  # Set ID — harmless

# ─────────────────────────────────────────────────────────────────────────────
# Synthetic data pools (structurally valid, clearly fake)
# NHS test number range: 999 000 0000 – 999 999 9999
# Ofcom test phone range: 07700 900000 – 07700 900999
# ─────────────────────────────────────────────────────────────────────────────

TEST_SURNAMES   = ["TESTPATIENT", "TESTERSON", "SAMPLEDATA", "DEMOUSER",
                   "SYNTHETIC", "FAKEPATIENT", "TESTCASE", "HEALTHTEST"]
TEST_FORENAMES  = ["ONE", "TWO", "THREE", "FOUR", "FIVE",
                   "ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON"]
TEST_STREETS    = ["1 TEST STREET", "2 SAMPLE ROAD", "3 DEMO LANE",
                   "4 SYNTHETIC AVENUE", "5 FAKE CLOSE"]
TEST_TOWNS      = ["TESTTOWN", "SAMPLEVILLE", "DEMOBOROUGH",
                   "SYNTHETICHAM", "FAKEFIELD"]
TEST_POSTCODES  = ["TE1 1ST", "SA1 1MP", "DE1 1MO", "FA1 1KE", "TE5 5ST"]
TEST_DOBS       = ["19700101", "19750615", "19801231", "19650401", "19900101"]
TEST_ACCOUNTS   = ["ACC-TEST-001", "ACC-TEST-002", "ACC-TEST-003"]


def _seed(real_value: str) -> random.Random:
    """Return a seeded RNG so the same real value always maps to the same fake value."""
    h = int(hashlib.md5(real_value.encode()).hexdigest(), 16)
    return random.Random(h)


def synthetic_nhs_number(real: str) -> str:
    rng = _seed(real)
    return "999" + str(rng.randint(0, 9_999_999)).zfill(7)


def synthetic_name_hl7(real_hl7_name: str) -> str:
    """Turn e.g. SMITH^JOHN^WILLIAM^^MR into TESTPATIENT^ONE^^^MR"""
    parts = real_hl7_name.split("^")
    rng = _seed(real_hl7_name)
    surname  = rng.choice(TEST_SURNAMES)
    forename = rng.choice(TEST_FORENAMES)
    title    = parts[4] if len(parts) > 4 else ""
    return f"{surname}^{forename}^^^{title}"


def synthetic_dob(real: str) -> str:
    rng = _seed(real)
    return rng.choice(TEST_DOBS)


def synthetic_address(real: str) -> str:
    rng = _seed(real)
    street   = rng.choice(TEST_STREETS)
    town     = rng.choice(TEST_TOWNS)
    postcode = rng.choice(TEST_POSTCODES)
    return f"{street}^^{town}^^{postcode}^GBR"


def synthetic_phone(_real: str) -> str:
    rng = _seed(_real)
    return "07700" + str(rng.randint(900000, 900999))


def synthetic_account(real: str) -> str:
    rng = _seed(real)
    return rng.choice(TEST_ACCOUNTS)


def synthetic_mrn(real: str) -> str:
    rng = _seed(real)
    return "MRN-TEST-" + str(rng.randint(10000, 99999))


# ─────────────────────────────────────────────────────────────────────────────
# PID anonymisation modes
# ─────────────────────────────────────────────────────────────────────────────

def pid_strip(_seg):
    return None


def pid_redact(seg, sep="|"):
    fields = seg.split(sep)
    for i in range(1, len(fields)):
        if i in PID_SENSITIVE_FIELDS and i not in KEEP_FIELDS and fields[i].strip():
            fields[i] = "REDACTED"
    return sep.join(fields)


def pid_blank(seg, sep="|"):
    fields = seg.split(sep)
    for i in range(1, len(fields)):
        if i in PID_SENSITIVE_FIELDS and i not in KEEP_FIELDS:
            fields[i] = ""
    return sep.join(fields)


def pid_pseudonymise(seg, sep="|"):
    """Replace each sensitive field with a structurally valid synthetic value."""
    fields = seg.split(sep)

    def get(i):
        return fields[i] if i < len(fields) else ""

    def put(i, v):
        while len(fields) <= i:
            fields.append("")
        fields[i] = v

    # PID-3: Patient Identifier List  e.g. 9876543210^^^NHS^NH~MR123456^^^MRN
    if get(3).strip():
        new_repeats = []
        for repeat in get(3).split("~"):
            parts = repeat.split("^")
            if parts[0].strip():
                id_type = parts[4].upper() if len(parts) > 4 else ""
                if id_type in ("NH", "NHS") or re.fullmatch(r"\d{10}", parts[0].strip()):
                    parts[0] = synthetic_nhs_number(parts[0])
                else:
                    parts[0] = synthetic_mrn(parts[0])
            new_repeats.append("^".join(parts))
        put(3, "~".join(new_repeats))

    # PID-2 external ID
    if get(2).strip():
        put(2, synthetic_mrn(get(2)))

    # PID-4 alternate ID
    if get(4).strip():
        put(4, synthetic_mrn(get(4)))

    # PID-5 patient name
    if get(5).strip():
        put(5, synthetic_name_hl7(get(5)))

    # PID-6 mother's maiden name
    if get(6).strip():
        put(6, "TESTMOTHER^TEST")

    # PID-7 DOB
    if get(7).strip():
        put(7, synthetic_dob(get(7)))

    # PID-8 sex — keep as-is (non-identifying, needed for LIS/pharmacy)
    # PID-9 alias
    if get(9).strip():
        put(9, "TESTALIAS^TEST")

    # PID-10 race / PID-22 ethnic group — blank (sensitive, not needed for testing)
    for i in (10, 22):
        put(i, "")

    # PID-11 address
    if get(11).strip():
        put(11, synthetic_address(get(11)))

    # PID-12 county code
    put(12, "")

    # PID-13 home phone
    if get(13).strip():
        put(13, synthetic_phone(get(13)))

    # PID-14 business phone
    if get(14).strip():
        put(14, synthetic_phone(get(14)))

    # PID-15 language, PID-16 marital status, PID-17 religion — keep (non-identifying)

    # PID-18 account number
    if get(18).strip():
        put(18, synthetic_account(get(18)))

    # PID-19 national ID / SSN
    if get(19).strip():
        put(19, "TEST-ID-00000")

    # PID-20 driver licence
    if get(20).strip():
        put(20, "")

    # PID-21 mother's identifier
    if get(21).strip():
        put(21, synthetic_mrn(get(21)))

    # PID-23 birthplace
    if get(23).strip():
        put(23, "TESTTOWN")

    # PID-29 death date, PID-30 death indicator — blank
    for i in (29, 30):
        put(i, "")

    return sep.join(fields)


# ─────────────────────────────────────────────────────────────────────────────
# Free-text scrubbing (NTE, OBX, Z-segments)
# ─────────────────────────────────────────────────────────────────────────────

def extract_identifiers(pid_line, sep="|"):
    fields = pid_line.split(sep)
    ids = {"nhs_numbers": [], "names": []}

    for fi in (2, 3, 4):
        if fi < len(fields) and fields[fi].strip():
            for repeat in fields[fi].split("~"):
                val = repeat.split("^")[0].strip()
                if val:
                    ids["nhs_numbers"].append(val)

    for fi in (5, 6, 9):
        if fi < len(fields) and fields[fi].strip():
            for repeat in fields[fi].split("~"):
                parts = [p.strip() for p in repeat.split("^") if p.strip()]
                ids["names"].extend(p for p in parts if len(p) >= 3
                                    and p.upper() not in ("MR", "MRS", "MS", "DR", "MISS", "PROF"))
    return ids


def build_scrub_pattern(ids):
    terms = [re.escape(v) for v in ids["nhs_numbers"] if v]
    terms += [r"\b" + re.escape(n) + r"\b" for n in ids["names"] if len(n) >= 3]
    if not terms:
        return None
    return re.compile("|".join(terms), re.IGNORECASE)


def is_free_text_seg(name):
    return name in {"NTE", "OBX"} or name.startswith("Z")


def scrub_line(line, pattern, replacement):
    if pattern is None:
        return line
    return pattern.sub(replacement, line)


# ─────────────────────────────────────────────────────────────────────────────
# Core message processor
# ─────────────────────────────────────────────────────────────────────────────

def detect_sep(message):
    for line in message.splitlines():
        if line.startswith("MSH") and len(line) > 3:
            return line[3]
    return "|"


FREE_TEXT_REPLACEMENT = {
    "strip":         "[REMOVED]",
    "redact":        "[REDACTED]",
    "blank":         "",
    "pseudonymise":  "[REMOVED]",   # free-text can't be meaningfully pseudonymised
}

PID_FN = {
    "strip":        pid_strip,
    "redact":       pid_redact,
    "blank":        pid_blank,
    "pseudonymise": pid_pseudonymise,
}


def process_message(message, mode):
    sep   = detect_sep(message)
    lines = message.splitlines(keepends=True)

    # Pass 1 — collect real identifiers for free-text scrubbing
    all_ids = {"nhs_numbers": [], "names": []}
    for line in lines:
        if line[:3].upper() == "PID":
            ids = extract_identifiers(line.rstrip("\r\n"), sep)
            all_ids["nhs_numbers"].extend(ids["nhs_numbers"])
            all_ids["names"].extend(ids["names"])

    scrub_pat     = build_scrub_pattern(all_ids)
    ft_replace    = FREE_TEXT_REPLACEMENT[mode]
    pid_fn        = PID_FN[mode]
    stats         = {"pid": 0, "free_text": 0}
    result        = []

    for line in lines:
        seg = line[:3].upper()

        if seg == "PID":
            stats["pid"] += 1
            bare    = line.rstrip("\r\n")
            ending  = line[len(bare):]
            out     = pid_fn(bare, sep) if mode != "strip" else pid_fn(bare)
            if out is not None:
                result.append(out + ending)

        elif is_free_text_seg(seg):
            scrubbed = scrub_line(line, scrub_pat, ft_replace)
            if scrubbed != line:
                stats["free_text"] += 1
            result.append(scrubbed)

        else:
            result.append(line)

    return "".join(result), stats


# ─────────────────────────────────────────────────────────────────────────────
# Interactive UI helpers
# ─────────────────────────────────────────────────────────────────────────────

BANNER = r"""
  _   _ _     _____     _   _                     _
 | | | | |   |___  |   / \ | |__   ___  _ __  ___| |_ ___  _ __
 | |_| | |      / /   / _ \| '_ \ / _ \| '_ \/ __| __/ _ \| '__|
 |  _  | |___  / /   / ___ \ | | | (_) | | | \__ \ ||  __/| |
 |_| |_|_____|/_/   /_/   \_\_| |_|\___/|_| |_|___/\__\___||_|

         NHS HL7 Patient Data Anonymiser  v2.0
"""

MODES = {
    "1": {
        "key":   "pseudonymise",
        "label": "Pseudonymise  (recommended for downstream testing)",
        "desc":  (
            "Replaces real patient data with structurally valid synthetic values.\n"
            "  • NHS number → valid-format test number (999xxxxxxx)\n"
            "  • Name       → TESTPATIENT^ONE\n"
            "  • DOB        → kept plausible (e.g. 19700101)\n"
            "  • Address    → 1 TEST STREET, TESTTOWN\n"
            "  • Phone      → 07700 900xxx (Ofcom test range)\n"
            "  Best for: LIS, RIS, Pharmacy, EHR, medical device testing."
        ),
    },
    "2": {
        "key":   "redact",
        "label": "Redact  (audit / evidence trail)",
        "desc":  (
            "Replaces every sensitive field with the word REDACTED.\n"
            "  • Clearly shows data existed but has been removed.\n"
            "  Best for: audit logs, compliance reviews, incident reports.\n"
            "  Note: downstream systems may reject structurally invalid fields."
        ),
    },
    "3": {
        "key":   "blank",
        "label": "Blank  (preserve message structure, empty fields)",
        "desc":  (
            "Empties sensitive fields but keeps all segment delimiters intact.\n"
            "  • PID segment remains present with empty field values.\n"
            "  Best for: integration testing where segment presence matters\n"
            "  but actual values are irrelevant."
        ),
    },
    "4": {
        "key":   "strip",
        "label": "Strip  (remove entire PID segment)",
        "desc":  (
            "Deletes the PID segment from the message entirely.\n"
            "  • Smallest possible output.\n"
            "  Best for: anonymising messages where patient identity is\n"
            "  completely irrelevant (e.g. structural/schema validation only)."
        ),
    },
}


def hr(char="─", width=62):
    print(dim(char * width))


def print_banner():
    print(cyan(BANNER))


def ask(prompt, valid=None, default=None):
    """Prompt the user and return their answer, re-asking on invalid input."""
    hint = ""
    if valid:
        hint = "  [" + "/".join(valid) + "]"
    if default:
        hint += f"  (default: {default})"
    while True:
        try:
            answer = input(f"{bold(prompt)}{dim(hint)}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            print(yellow("\nExiting. No data was written to disk."))
            sys.exit(0)
        if not answer and default:
            return default
        if valid is None or answer in valid:
            return answer
        print(red(f"  Please enter one of: {', '.join(valid)}"))


def choose_mode():
    hr()
    print(bold("\nStep 1 of 2 — Choose anonymisation mode\n"))
    for k, m in MODES.items():
        print(f"  {bold(cyan(k))}.  {m['label']}")
    print()
    for k, m in MODES.items():
        print(f"  {bold(k)}) {m['desc']}\n")

    choice = ask("Enter mode number", valid=list(MODES.keys()), default="1")
    mode   = MODES[choice]["key"]
    print(green(f"\n  ✓ Mode selected: {MODES[choice]['label']}\n"))
    return mode


def read_paste():
    hr()
    print(bold("\nStep 2 of 2 — Paste your HL7 message\n"))
    print("  Paste the full HL7 message into this window.")
    print("  When you have pasted everything, signal end-of-input:\n")
    print(f"    {cyan('Mac / Linux')} →  press  {bold('Ctrl + D')}")
    print(f"    {cyan('Windows')}     →  press  {bold('Ctrl + Z')}  then  {bold('Enter')}\n")
    hr("·")
    try:
        raw = sys.stdin.read()
    except (KeyboardInterrupt, EOFError):
        print()
        print(yellow("\nCancelled. No data was processed."))
        sys.exit(0)
    return raw


def print_result(anonymised, stats, mode):
    hr()
    print(bold(green("\n  ✓ Anonymisation complete\n")))
    print(f"  Mode              : {bold(mode)}")
    print(f"  PID segments      : {bold(str(stats['pid']))} processed")
    print(f"  Free-text lines   : {bold(str(stats['free_text']))} scrubbed (NTE / OBX / Z-segments)")
    print(dim("  Nothing was written to disk — message is in-memory only.\n"))
    hr("═")
    print(bold(cyan("\n  ANONYMISED MESSAGE\n")))
    hr("═")
    print(anonymised)
    hr("═")
    print(dim("\n  Copy the message above. It contains no real patient data.\n"))


def ask_again():
    hr()
    again = ask("Anonymise another message?", valid=["y", "n"], default="n")
    return again == "y"


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print_banner()
    print(dim("  No data is stored to disk. Everything stays in memory.\n"))

    while True:
        mode = choose_mode()
        raw  = read_paste()

        if not raw.strip():
            print(red("\n  No input detected. Please try again.\n"))
            continue

        anonymised, stats = process_message(raw, mode)
        print_result(anonymised, stats, mode)

        if not ask_again():
            print(green("\n  Goodbye. Stay compliant! 👋\n"))
            break


if __name__ == "__main__":
    main()
