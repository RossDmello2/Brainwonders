import asyncio
import json
import logging
import uuid

import httpx
import pytest
import pytest_asyncio

from app.main import app

ORIGIN = {"Origin":"http://127.0.0.1:8080"}


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://api") as value:
        yield value


@pytest.mark.asyncio
async def test_health_contract_and_no_store(client):
    response=await client.get("/health")
    assert response.json()=={"status":"ok","api_version":"1","template_schema_versions":["1.0"]}
    assert response.headers["cache-control"]=="no-store" and response.headers["x-request-id"]
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_cleanup_failure_fails_readiness(client):
    import app.main as main_module
    class BadUpload:
        async def read(self,_maximum): return b"x"
        async def close(self): raise OSError("synthetic cleanup failure")
    try:
        with pytest.raises(Exception) as exc:
            await main_module._read(BadUpload(),10)
        assert getattr(exc.value,"code",None)=="CLEANUP_FAILED"
        response=await client.get("/health")
        assert response.status_code==503 and response.json()["error"]["code"]=="SERVICE_NOT_READY"
    finally:
        main_module.ready=True


@pytest.mark.asyncio
async def test_post_origin_is_exact(client,wav_bytes):
    response=await client.post("/v1/transcriptions",files={"audio":("a.wav",wav_bytes)},data={},headers={"Origin":"https://evil.test"})
    assert response.status_code==403 and response.json()["error"]["code"]=="ORIGIN_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_aggregate_headers_are_bounded(client):
    response=await client.get("/health",headers={"X-Filler":"x"*17_000})
    assert response.status_code==400 and response.json()["error"]["code"]=="REQUEST_INVALID"


@pytest.mark.asyncio
async def test_cors_preflight_never_contacts_provider(client):
    response=await client.options("/v1/transcriptions",headers={**ORIGIN,"Access-Control-Request-Method":"POST","Access-Control-Request-Headers":"X-Provider-Key"})
    assert response.status_code==204 and response.headers["access-control-allow-origin"]==ORIGIN["Origin"]


def transcription_parts(wav_bytes,**overrides):
    data={"provider":"groq","model":"whisper-large-v3-turbo","language":"en","capture_source":"upload","client_duration_seconds":"0.1","duration_unknown_acknowledged":"false"}
    data.update(overrides);return data,{"audio":("a.wav",wav_bytes,"audio/wav")}


@pytest.mark.asyncio
async def test_mocked_transcription_success(client,wav_bytes):
    seen={}
    def handler(request):
        seen["url"]=str(request.url);seen["auth"]=request.headers.get("authorization")
        return httpx.Response(200,json={"text":"Fictional dictated text.","language":"en"})
    app.state.provider_transport=httpx.MockTransport(handler)
    data,files=transcription_parts(wav_bytes)
    response=await client.post("/v1/transcriptions",data=data,files=files,headers={**ORIGIN,"X-Provider-Key":"test-key-only"})
    assert response.status_code==200 and response.json()["text"]=="Fictional dictated text."
    assert seen=={"url":"https://api.groq.com/openai/v1/audio/transcriptions","auth":"Bearer test-key-only"}
    assert "test-key-only" not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("upstream,code,status",[(401,"PROVIDER_KEY_REJECTED",422),(403,"PROVIDER_KEY_REJECTED",422),(402,"PROVIDER_PAYMENT_REQUIRED",402),(429,"PROVIDER_RATE_LIMITED",429),(500,"PROVIDER_UNAVAILABLE",502)])
async def test_provider_errors_are_normalized(client,wav_bytes,upstream,code,status):
    app.state.provider_transport=httpx.MockTransport(lambda _r:httpx.Response(upstream,text="TEST_SECRET_DO_NOT_PERSIST_CANARY",headers={"Retry-After":"30"}))
    data,files=transcription_parts(wav_bytes);response=await client.post("/v1/transcriptions",data=data,files=files,headers={**ORIGIN,"X-Provider-Key":"canary-key"})
    assert response.status_code==status and response.json()["error"]["code"]==code
    assert "CANARY" not in response.text and "canary-key" not in response.text
    if upstream==429: assert response.json()["error"]["retry_after_seconds"]==30


@pytest.mark.asyncio
async def test_provider_timeout(client,wav_bytes):
    async def handler(_request):
        raise httpx.ReadTimeout("TEST_SECRET_DO_NOT_PERSIST_TIMEOUT")
    app.state.provider_transport=httpx.MockTransport(handler)
    data,files=transcription_parts(wav_bytes);response=await client.post("/v1/transcriptions",data=data,files=files,headers={**ORIGIN,"X-Provider-Key":"canary"})
    assert response.status_code==504 and response.json()["error"]["code"]=="PROVIDER_TIMEOUT"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload",[{}, {"words":[]}, {"text":"   "}, {"text":123}])
async def test_malformed_and_empty_provider_response(client,wav_bytes,payload):
    app.state.provider_transport=httpx.MockTransport(lambda _r:httpx.Response(200,json=payload))
    data,files=transcription_parts(wav_bytes);response=await client.post("/v1/transcriptions",data=data,files=files,headers={**ORIGIN,"X-Provider-Key":"canary"})
    assert response.status_code in (422,502)
    assert response.json()["error"]["code"] in ("NO_SPEECH_RECOGNIZED","PROVIDER_RESPONSE_INVALID")


@pytest.mark.asyncio
async def test_invalid_key_never_contacts_provider(client,wav_bytes):
    called=False
    def handler(_r):
        nonlocal called;called=True;return httpx.Response(200,json={"text":"bad"})
    app.state.provider_transport=httpx.MockTransport(handler)
    data,files=transcription_parts(wav_bytes);response=await client.post("/v1/transcriptions",data=data,files=files,headers={**ORIGIN,"X-Provider-Key":"bad key\t"})
    assert response.status_code==422 and not called


@pytest.mark.asyncio
async def test_duplicate_key_headers_are_rejected_before_relay(client,wav_bytes):
    called=False
    def handler(_request):
        nonlocal called;called=True;return httpx.Response(200,json={"text":"bad"})
    app.state.provider_transport=httpx.MockTransport(handler)
    data,files=transcription_parts(wav_bytes)
    headers=[("Origin",ORIGIN["Origin"]),("X-Provider-Key","first"),("X-Provider-Key","second")]
    response=await client.post("/v1/transcriptions",data=data,files=files,headers=headers)
    assert response.status_code==400 and response.json()["error"]["code"]=="REQUEST_INVALID" and not called


@pytest.mark.asyncio
async def test_provider_response_model_must_match_request(client,wav_bytes):
    app.state.provider_transport=httpx.MockTransport(
        lambda _r:httpx.Response(200,json={"text":"Fictional text.","model":"different-model"}))
    data,files=transcription_parts(wav_bytes)
    response=await client.post("/v1/transcriptions",data=data,files=files,headers={**ORIGIN,"X-Provider-Key":"canary"})
    assert response.status_code==502 and response.json()["error"]["code"]=="PROVIDER_RESPONSE_INVALID"


@pytest.mark.asyncio
async def test_runtime_secret_canary_not_in_responses_logs_workspace_or_docx(client,wav_bytes,pair,values,caplog):
    from pathlib import Path
    from app.services.template_engine import generate_docx, validate_pair
    canary="TEST_SECRET_DO_NOT_PERSIST_"+uuid.uuid4().hex
    data,files=transcription_parts(wav_bytes)
    headers={**ORIGIN,"X-Provider-Key":canary}
    caplog.set_level(logging.INFO,logger="cls.outcome")
    app.state.provider_transport=httpx.MockTransport(lambda _r:httpx.Response(200,json={"text":"Synthetic success.","language":"en"}))
    success=await client.post("/v1/transcriptions",data=data,files=files,headers=headers)
    app.state.provider_transport=httpx.MockTransport(lambda _r:httpx.Response(500,text=canary))
    _,files=transcription_parts(wav_bytes)
    failure=await client.post("/v1/transcriptions",data=data,files=files,headers=headers)
    assert success.status_code==200 and failure.status_code==502
    assert canary not in success.text+failure.text+caplog.text
    docx,config=pair;generated,_=generate_docx(docx,config,values,validate_pair(docx,config)["fingerprint"])
    assert canary.encode() not in generated
    root=Path(__file__).parents[1]
    matches=[]
    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            try:
                if canary.encode() in path.read_bytes(): matches.append(path)
            except OSError: pass
    assert matches==[]


@pytest.mark.asyncio
async def test_invalid_model_and_arbitrary_url_rejected(client,wav_bytes):
    data,files=transcription_parts(wav_bytes,model="user-model",url="http://127.0.0.1")
    response=await client.post("/v1/transcriptions",data=data,files=files,headers={**ORIGIN,"X-Provider-Key":"canary"})
    assert response.status_code in (400,503)


@pytest.mark.asyncio
async def test_empty_unsupported_and_large_audio(client,wav_bytes):
    data,_=transcription_parts(wav_bytes)
    for body,expected in [(b"","AUDIO_EMPTY"),(b"plain text","AUDIO_FORMAT_UNSUPPORTED")]:
        r=await client.post("/v1/transcriptions",data=data,files={"audio":("x.bin",body)},headers={**ORIGIN,"X-Provider-Key":"canary"})
        assert r.json()["error"]["code"]==expected
    r=await client.post("/v1/transcriptions",data=data,files={"audio":("x.wav",b"0"*(8_388_609))},headers={**ORIGIN,"X-Provider-Key":"canary"})
    assert r.status_code==413


@pytest.mark.asyncio
async def test_template_validate_and_document_roundtrip(client,pair,values):
    docx,config=pair
    response=await client.post("/v1/templates/validate",files={"template_docx":("template.docx",docx),"template_json":("template.json",config)},headers=ORIGIN)
    assert response.status_code==200,response.text
    fingerprint=response.json()["fingerprint"]
    response=await client.post("/v1/documents/docx",files={"template_docx":("template.docx",docx),"template_json":("template.json",config),"values_json":("values.json",values)},data={"expected_fingerprint":fingerprint,"review_confirmed":"true"},headers=ORIGIN)
    assert response.status_code==200,response.text
    assert response.content[:2]==b"PK" and "example-DEMO-000.docx" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_document_requires_review_and_current_pair(client,pair,values):
    from app.services.template_engine import fingerprint
    docx,config=pair
    base={"template_docx":("template.docx",docx),"template_json":("template.json",config),"values_json":("values.json",values)}
    response=await client.post("/v1/documents/docx",files=base,data={"expected_fingerprint":fingerprint(docx,config),"review_confirmed":"false"},headers=ORIGIN)
    assert response.status_code==422 and response.json()["error"]["code"]=="REVIEW_REQUIRED"
    response=await client.post("/v1/documents/docx",files=base,data={"expected_fingerprint":"0"*64,"review_confirmed":"true"},headers=ORIGIN)
    assert response.status_code==409 and response.json()["error"]["code"]=="TEMPLATE_CHANGED"
