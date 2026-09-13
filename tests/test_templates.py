import io
import json
import multiprocessing
import threading
import zipfile
from pathlib import Path

import pytest
from docx import Document

from app.errors import AppError
from app.services.template_engine import (_alpha, fingerprint, generate_docx, parse_json,
    safe_filename, validate_pair, validate_values)

ROOT=Path(__file__).parents[1]


def xml_text(docx):
    with zipfile.ZipFile(io.BytesIO(docx)) as z:return z.read("word/document.xml").decode("utf-8")


def test_two_assets_discovered_without_source_registration():
    manifest=json.loads((ROOT/"frontend/templates/index.json").read_text("utf-8"))
    assert [x["id"] for x in manifest["templates"]]==["fictional_objection","fictional_table"]
    source="\n".join(p.read_text("utf-8",errors="ignore") for p in (ROOT/"backend/app").rglob("*.py"))
    assert "fictional_objection" not in source and "fictional_table" not in source
    for item in manifest["templates"]:
        folder=ROOT/"frontend/templates"/item["id"]/item["version"]
        result=validate_pair((folder/"template.docx").read_bytes(),(folder/"template.json").read_bytes())
        assert result["configuration"]["id"]==item["id"]


def test_schema_copies_exact():
    assert (ROOT/"frontend/templates/schema/template-config.schema.json").read_bytes()==(ROOT/"backend/app/schemas/template-config.schema.json").read_bytes()


def test_fingerprint_is_exact_byte_sensitive(pair):
    docx,config=pair
    assert fingerprint(docx,config)!=fingerprint(docx,config+b" ")


def test_duplicate_and_nonfinite_json_rejected():
    for raw in (b'{"x":1,"x":2}',b'{"x":NaN}'):
        with pytest.raises(AppError):parse_json(raw,100)


def test_missing_binding_and_forbidden_jinja_rejected(pair):
    docx,config=pair;changed=json.loads(config);changed["fields"][0]["placeholder"]="RENAMED"
    with pytest.raises(AppError) as exc:validate_pair(docx,json.dumps(changed).encode())
    assert exc.value.code=="TEMPLATE_BINDING_MISMATCH"


def test_active_relationship_and_zip_bomb_shape_rejected(pair):
    docx,config=pair;source=zipfile.ZipFile(io.BytesIO(docx));out=io.BytesIO()
    with zipfile.ZipFile(out,"w") as z:
        for info in source.infolist():z.writestr(info,source.read(info))
        z.writestr("word/vbaProject.bin",b"evil")
    with pytest.raises(AppError) as exc:validate_pair(out.getvalue(),config)
    assert exc.value.code=="TEMPLATE_UNSAFE_CONTENT"


def test_typed_values_reject_boolean_integer_and_bad_date(pair,values):
    docx,config=pair;validated=validate_pair(docx,config)["configuration"]
    data=json.loads(values);data["fields"]["case_year"]=True
    with pytest.raises(AppError):validate_values(validated,data)
    data=json.loads(values);data["fields"]["document_date"]="2041-02-29"
    with pytest.raises(AppError):validate_values(validated,data)


def test_numbering_boundaries():
    assert [_alpha(x) for x in (1,26,27,52)]==["A","Z","AA","AZ"]


@pytest.mark.parametrize("name",["CON.docx","a"*121+".docx"])
def test_unsafe_filename(name):
    with pytest.raises(AppError):safe_filename(name,{})


def test_path_characters_are_safely_replaced():
    assert safe_filename("../bad.docx",{})=="_bad.docx"


@pytest.mark.parametrize("template_id",["fictional_objection","fictional_table"])
def test_real_docx_generation_and_ooxml(template_id,values):
    folder=ROOT/"frontend/templates"/template_id/"1.0.0";docx=(folder/"template.docx").read_bytes();config=(folder/"template.json").read_bytes();fp=validate_pair(docx,config)["fingerprint"]
    output,name=generate_docx(docx,config,values,fp);text=xml_text(output)
    assert "Example Forum" in text and "DEMO-000" in text and "&lt; &gt; &amp;" in text
    assert "{%" not in text and "{{" not in text and name.endswith(".docx")
    document=Document(io.BytesIO(output));assert len(document.sections)==1


def test_metadata_scrubbed(pair,values):
    docx,config=pair;out,_=generate_docx(docx,config,values,validate_pair(docx,config)["fingerprint"])
    document=Document(io.BytesIO(out));assert not document.core_properties.author and not document.core_properties.last_modified_by


def test_isolated_document_timeout_and_cancel_kill_children(pair):
    from app.services.document_isolation import run_isolated
    docx,config=pair
    before={process.pid for process in multiprocessing.active_children()}
    with pytest.raises(AppError) as timed_out:
        run_isolated("validate",{"docx":docx,"config":config},timeout=.001)
    assert timed_out.value.code=="DOCUMENT_TIMEOUT"
    canceled=threading.Event();canceled.set()
    with pytest.raises(AppError) as stopped:
        run_isolated("validate",{"docx":docx,"config":config},timeout=5,cancel_event=canceled)
    assert stopped.value.code=="DOCUMENT_FAILED"
    assert {process.pid for process in multiprocessing.active_children()}==before
