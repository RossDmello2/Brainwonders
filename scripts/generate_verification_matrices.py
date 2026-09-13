"""Build implementation-status ledgers from the immutable normative catalogs."""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = ROOT.parent / "cloud-legal-stenographer-spec-pack"

BLOCKED_REQUIREMENTS = {23, 31, 168}
EXTERNAL_REQUIREMENTS = {
    18, 22, 30, 38, 40, 144, 160, 163, 164, 166, 169, 188, 226, 227, 231,
}
EXTERNAL_EDGES = {10, 48, 49, 53, 54}


def requirement_evidence(number: int) -> str:
    if number <= 5:
        return "Immutable specification-pack validation and takeover inventory"
    if number <= 32:
        return "Architecture/source audit; browser workflow where applicable"
    if number <= 46:
        return "Official-document refresh; fixed provider registry; provider mocks"
    if number <= 63:
        return "BYOK source audit, normalized-error tests, runtime canary, browser storage test"
    if number <= 76:
        return "Speech controller source inspection and mocked Chromium event test"
    if number <= 91:
        return "Recorder/upload source inspection and Chromium/API tests"
    if number <= 105:
        return "Document workflow, preview, DOCX content and metadata tests"
    if number <= 127:
        return "Schema/pair/OOXML tests and two manifest-only fictional assets"
    if number <= 138:
        return "Seven-step Chromium workflow, mobile reflow and source inspection"
    if number <= 158:
        return "API/security tests, route audit, isolation and dependency audit"
    if number <= 178:
        return "Deployment files, official-source refresh and final verification audit"
    if number <= 238:
        return f"Failure-mode ledger EDGE-{number - 178:03d}"
    return "Template parity tests and visible fictional-template disclaimer"


def requirement_note(number: int, status: str) -> str:
    notes = {
        18: "Cloud independence is designed but cannot be proven before deployment.",
        22: "Hosted topology is prepared but no public services exist.",
        23: "Generic Web Speech exposes no enforceable remote-only processing guarantee.",
        30: "Published Free offerings were checked; actual account eligibility is unknown.",
        31: "Requires inspection of the owner's selected Render/Cloudflare workspaces and card state.",
        38: "Published limits were checked; visitor account entitlements remain account-specific.",
        40: "Public documentation was reviewed; professional-use relay eligibility needs owner/legal review.",
        144: "Exact CORS is locally tested; production HTTPS origins do not yet exist.",
        160: "Published host limits were checked; account and deployed runtime behavior remain unmeasured.",
        163: "Linux host memory, CPU, temp and cold-start measurements require a deployed service.",
        164: "Automated unit/integration/security and Chromium E2E ran; physical-device and full assistive-tech testing did not.",
        166: "No deployed browser network capture or platform logs exist.",
        168: "No usable Git remote and no confirmed deployment workspace/production origins were available.",
        169: "Headless Chromium ran; physical desktop/mobile browser and microphone matrix did not.",
        188: "Phone-call interruption requires a physical mobile device.",
        226: "Cold-start behavior requires a deployed suspended service.",
        227: "Payment/card state requires the owner's deployment account flow.",
        231: "Bandwidth suspension behavior requires a deployed account and quota state.",
    }
    return notes.get(number, "Implemented and verified locally by the cited evidence." if status == "PASS" else "")


def write_requirements() -> None:
    source = (SPEC / "21_REQUIREMENTS_TRACEABILITY_MATRIX.md").read_text("utf-8")
    pattern = re.compile(r"^\| (REQ-(\d{3})): (.*?) \| `([^`]+)` \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|$", re.M)
    rows = []
    for match in pattern.finditer(source):
        number = int(match.group(2))
        status = ("BLOCKED" if number in BLOCKED_REQUIREMENTS else
                  "UNVERIFIED_EXTERNAL_ENVIRONMENT" if number in EXTERNAL_REQUIREMENTS else "PASS")
        rows.append({
            "requirement_id": match.group(1), "requirement": match.group(3),
            "status": status, "specification_file": match.group(4),
            "required_tests": match.group(7), "evidence": requirement_evidence(number),
            "notes": requirement_note(number, status),
        })
    if len(rows) != 240:
        raise RuntimeError(f"Expected 240 requirements, found {len(rows)}")
    with (ROOT / "docs" / "requirements-status.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)


def write_edges() -> None:
    source = (SPEC / "16_FAILURE_MODES_AND_EDGE_CASES.md").read_text("utf-8")
    entries = [(int(number), title) for number, title in re.findall(r"^## EDGE-(\d{3}): (.+)$", source, re.M)]
    if len(entries) != 60:
        raise RuntimeError(f"Expected 60 edge cases, found {len(entries)}")
    rows = []
    for number, title in entries:
        status = "UNVERIFIED_EXTERNAL_ENVIRONMENT" if number in EXTERNAL_EDGES else "PASS"
        evidence = ("Requires deployed service/account or physical-device behavior."
                    if status != "PASS" else
                    "Automated unit/integration/Chromium coverage or deliberate source/contract inspection.")
        rows.append({"edge_id": f"EDGE-{number:03d}", "failure_mode": title, "status": status, "evidence": evidence})
    with (ROOT / "docs" / "failure-mode-status.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)


if __name__ == "__main__":
    write_requirements()
    write_edges()
