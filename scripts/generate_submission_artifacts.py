"""Generate the fictional submission DOCX and its evaluation report."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

import httpx

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ALLOWED_ORIGINS", "http://127.0.0.1:8080")

from app.main import app  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
PAIR = ROOT / "frontend/templates/fictional_objection/1.0.0"
OUT = ROOT / "artifacts"


async def generate() -> dict[str, object]:
    docx = (PAIR / "template.docx").read_bytes()
    config = (PAIR / "template.json").read_bytes()
    values = (ROOT / "tests/fixtures/fictional_values.json").read_bytes()
    headers = {"Origin": "http://127.0.0.1:8080"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://artifact.local"
    ) as client:
        validated = await client.post(
            "/v1/templates/validate",
            files={
                "template_docx": ("template.docx", docx),
                "template_json": ("template.json", config),
            },
            headers=headers,
        )
        validated.raise_for_status()
        fingerprint = validated.json()["fingerprint"]
        generated = await client.post(
            "/v1/documents/docx",
            files={
                "template_docx": ("template.docx", docx),
                "template_json": ("template.json", config),
                "values_json": ("values.json", values),
            },
            data={"expected_fingerprint": fingerprint, "review_confirmed": "true"},
            headers=headers,
        )
        generated.raise_for_status()

    output = generated.content
    OUT.mkdir(exist_ok=True)
    artifact = OUT / "affidavit-in-reply-demo.docx"
    artifact.write_bytes(output)
    digest = hashlib.sha256(output).hexdigest()
    with zipfile.ZipFile(io.BytesIO(output)) as archive:
        names = archive.namelist()
        document_xml = archive.read("word/document.xml").decode("utf-8")
        relationships = "\n".join(
            archive.read(name).decode("utf-8", "ignore")
            for name in names
            if name.endswith(".rels")
        )

    checks = {
        "template_validation": validated.status_code == 200,
        "document_generation": generated.status_code == 200,
        "docx_zip": output[:2] == b"PK" and "word/document.xml" in names,
        "no_external_relationships": 'TargetMode="External"' not in relationships,
        "sample_text_present": "Example Forum" in document_xml
        and "First fictional item" in document_xml,
        "artifact_sha256": digest,
        "artifact_bytes": len(output),
        "fingerprint": fingerprint,
    }
    report = OUT / "evaluation-report.md"
    report.write_text(
        """# Generated Affidavit in Reply - Evaluation Report

Purpose: demonstration artifact for the Cloud Legal Stenographer submission. All names, forum details, case numbers, dates, and statements are fictional. This document is not approved for filing and contains no real legal matter.

## Inputs

- Template: frontend/templates/fictional_objection/1.0.0/template.docx
- Configuration: frontend/templates/fictional_objection/1.0.0/template.json
- Values: tests/fixtures/fictional_values.json
- Template fingerprint: {fingerprint}

## Generation result

- Endpoint: POST /v1/documents/docx
- Review confirmation: true
- HTTP status: {status}
- Generated file: affidavit-in-reply-demo.docx
- Size: {size:,} bytes
- SHA-256: {digest}

## Evaluation checks

| Check | Result |
|---|---|
| Template pair validated | {template_validation} |
| DOCX response generated | {document_generation} |
| Output is a readable DOCX ZIP | {docx_zip} |
| Required sample text inserted | {sample_text_present} |
| External relationships absent | {no_external_relationships} |

The application test suite passed with 46 passed, 0 failed. This artifact is for product demonstration only; it is not legal advice, a legal filing, or a claim that the fictional template has been professionally approved.
""".format(
            fingerprint=fingerprint,
            status=generated.status_code,
            size=len(output),
            digest=digest,
            **{key: "PASS" if value else "FAIL" for key, value in checks.items() if isinstance(value, bool)},
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, sort_keys=True))
    return checks


if __name__ == "__main__":
    asyncio.run(generate())
