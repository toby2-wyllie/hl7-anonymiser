# NHS HL7 Patient Data Anonymiser

A lightweight, interactive command-line tool for anonymising sensitive NHS patient data from HL7 v2.x messages. Designed to support safe integration testing across NHS downstream systems — including Lab Information Systems (LIS), Radiology Information Systems (RIS), Electronic Health Records (EHR), Pharmacy systems, and medical devices — without exposing real patient data.

No third-party dependencies. No data written to disk. Just run and paste.

---

## Why This Tool Exists

When testing NHS integrations, real HL7 messages are often the only realistic source of test data. Sharing or storing those messages — even temporarily — risks exposing sensitive patient information including NHS numbers, names, addresses, and clinical data.

This tool lets you paste a real HL7 message directly into your terminal, anonymise it instantly in memory, and copy the safe output — without ever saving the original to a file.

---

## Features

- **Interactive guided menu** — no flags or configuration required
- **Four anonymisation modes** suited to different testing needs
- **NHS number scrubbing** from PID segments and free-text fields (NTE, OBX, Z-segments)
- **Patient name scrubbing** from free-text segments
- **Nothing written to disk** — all processing is in-memory
- **No third-party dependencies** — standard Python 3.7+ only
- **Deterministic pseudonymisation** — same real value always maps to the same synthetic value, preserving referential integrity across linked messages

---

## Anonymisation Modes

| Mode | What it does | Best for |
|---|---|---|
| **Pseudonymise** *(recommended)* | Replaces real data with structurally valid synthetic values | LIS, RIS, Pharmacy, EHR, medical device testing |
| **Redact** | Replaces sensitive fields with `REDACTED` | Audit logs, compliance reviews, incident reports |
| **Blank** | Empties sensitive fields, preserves segment structure | Integration testing where segment presence matters |
| **Strip** | Removes the entire PID segment | Schema/structural validation only |

### Pseudonymise mode — synthetic value mapping

| Field | Real value | Synthetic replacement |
|---|---|---|
| NHS Number | `9876543210` | `999xxxxxxx` (NHS test range) |
| Name | `SMITH^JOHN^WILLIAM^^MR` | `TESTPATIENT^ONE^^^MR` |
| Date of Birth | `19800101` | Plausible synthetic DOB |
| Address | `12 High Street, London, SW1A 1AA` | `1 TEST STREET^^TESTTOWN^^TE1 1ST^GBR` |
| Phone (Home) | `07911234567` | `07700900xxx` (Ofcom test range) |
| Phone (Work) | `02071234567` | `07700900xxx` (Ofcom test range) |
| MRN | `MR123456` | `MRN-TEST-xxxxx` |
| Account Number | `ACC123456` | `ACC-TEST-001` |

Synthetic values use the **NHS England reserved test number range** (`999 000 0000 – 999 999 9999`) and **Ofcom reserved test phone numbers** (`07700 900000 – 07700 900999`), so downstream systems that validate these formats will accept them without triggering real patient workflows.

---

## Requirements

- Python 3.7 or later
- No additional packages required

---

## Installation

```bash
# Clone or download the script
git clone https://github.com/your-org/hl7-anonymiser.git
cd hl7-anonymiser

# Or just download the single file
curl -O https://raw.githubusercontent.com/your-org/hl7-anonymiser/main/hl7_anonymise.py

---

## Usage

### Interactive mode (recommended)

```bash
python hl7_anonymise.py
```

The tool will guide you through:

1. Choosing an anonymisation mode
2. Pasting your HL7 message
3. Copying the anonymised output

When you have finished pasting your message, signal end-of-input:

- **Mac / Linux:** `Ctrl + D`
- **Windows:** `Ctrl + Z` then `Enter`

### File mode (for batch processing)

Although the interactive paste mode is recommended to avoid storing real patient data, file mode is available for batch workflows where input files have already been appropriately secured:

```bash
# Single file
python hl7_anonymise.py --input patient.hl7 --mode pseudonymise

# Directory of .hl7 files
python hl7_anonymise.py --input ./inbox/ --output ./processed/ --mode pseudonymise

# Available flags
#   --input  / -i   Input file or directory
#   --output / -o   Output file or directory (defaults to <name>_anonymised)
#   --mode   / -m   pseudonymise | redact | blank | strip  (default: strip)
```

---

## What Gets Anonymised

### PID segment fields

All 30 PID fields containing patient-identifiable information are processed, including:

- PID-2/3/4: Patient identifiers and NHS number
- PID-5: Patient name
- PID-6: Mother's maiden name
- PID-7: Date of birth
- PID-8: Administrative sex *(retained in pseudonymise mode — needed for LIS/pharmacy dosing logic)*
- PID-11: Patient address
- PID-13/14: Phone numbers
- PID-18: Account number
- PID-19: National ID / SSN
- PID-22: Ethnic group
- PID-29/30: Death date and indicator

### Free-text segments

NHS numbers and patient names extracted from the PID segment are also scrubbed from:

- `NTE` — notes and comments
- `OBX` — observation results
- `Z*` — all custom Z-segments (e.g. `ZPD`, `ZPI`)

---

## Limitations

- Free-text scrubbing covers known segment types. Clinical narrative embedded in unexpected segments (e.g. `FT` formatted text fields) may require manual review.
- `NTE`/`OBX` free-text lines containing patient data are replaced with `[REMOVED]` in pseudonymise mode, as free-text cannot be meaningfully pseudonymised.
- This tool processes HL7 v2.x pipe-delimited messages. HL7 v3 / FHIR (XML/JSON) formats are not supported.

---

## Data Protection Notice

This tool is designed to assist with GDPR and NHS DSPT compliance by minimising the handling of real patient data during system testing. However:

- It is the **user's responsibility** to ensure that real patient data is handled lawfully and in accordance with your organisation's data protection policies.
- Do not paste real HL7 messages into shared terminals, CI/CD pipelines, or any environment where the terminal output may be logged.
- This tool is provided as-is. See the [License](LICENSE) for full terms.

---

## Contributing

Contributions are welcome. Please open an issue before submitting a pull request for significant changes.

---

## Special Thanks

This tool was built with the support and input of colleagues who helped shape its design and ensure it meets real-world NHS integration testing needs.

Sincere thanks to:

**Benita** · **Angela** · **Charlotte** · **Samir** · **Sanah**

Your expertise, feedback, and encouragement made this tool what it is <3

---

## License

MIT License — see [LICENSE](LICENSE) for full terms.
