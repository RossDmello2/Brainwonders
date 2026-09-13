import io
import os
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).parents[1]


@pytest.fixture(scope="module")
def live_servers():
    env=os.environ.copy();env.update(APP_ENV="development",ALLOWED_ORIGINS="http://127.0.0.1:8080",PYTHONPATH=str(ROOT/"backend"))
    flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
    backend=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000","--no-access-log"],cwd=ROOT/"backend",env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    frontend=subprocess.Popen([sys.executable,"-m","http.server","8080","--bind","127.0.0.1"],cwd=ROOT/"frontend",stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    try:
        for _ in range(80):
            try:
                if urllib.request.urlopen("http://127.0.0.1:8000/health",timeout=.3).status==200 and urllib.request.urlopen("http://127.0.0.1:8080",timeout=.3).status==200:break
            except Exception:time.sleep(.1)
        else:pytest.fail("Local servers did not start")
        yield
    finally:
        for process in (frontend,backend):
            process.terminate()
            try:process.wait(5)
            except subprocess.TimeoutExpired:process.kill()


def wav_bytes():
    import wave
    out=io.BytesIO()
    with wave.open(out,"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(8000);f.writeframes(b"\0\0"*800)
    return out.getvalue()


def fill_document(page):
    page.get_by_role("button",name="Add item").click()
    for element in page.locator("#field-container input, #field-container textarea, #field-container select").all():
        if not element.is_visible():continue
        tag=element.evaluate("e=>e.tagName")
        kind=element.get_attribute("type")
        required=element.get_attribute("required") is not None
        if tag=="SELECT":
            if required:element.select_option(index=1)
        elif kind=="date":element.fill("2040-01-02")
        elif element.get_attribute("data-field-type")=="integer":element.fill("2040")
        elif required:element.fill("<img src=x onerror=alert(1)> & reviewed value")


def test_full_browser_workflow_and_storage(live_servers,tmp_path):
    console=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(accept_downloads=True,viewport={"width":1280,"height":900})
        page=context.new_page();page.on("console",lambda message:console.append(message.text) if message.type=="error" else None)
        page.goto("http://127.0.0.1:8080",wait_until="networkidle")
        assert page.locator("section.step").count()==7
        page.locator("#template-select").select_option("fictional_objection")
        page.wait_for_function("document.querySelector('#template-status').textContent.includes('Fictional objection')",timeout=15000)
        assert page.locator("#field-container label").count()>=17
        fill_document(page)
        page.locator('[data-field="case_number"]').fill("DEMO-E2E")
        page.locator("#review-confirmed").check();page.locator("#refresh-preview").click()
        assert page.locator("#preview img").count()==0
        assert "<img src=x onerror=alert(1)>" in page.locator("#preview").inner_text()
        with page.expect_download(timeout=20000) as download_info:page.locator("#generate-docx").click()
        download=download_info.value;target=tmp_path/download.suggested_filename;download.save_as(target)
        assert target.name=="example-DEMO-E2E.docx"
        with zipfile.ZipFile(target) as z:
            document=z.read("word/document.xml").decode("utf-8")
            assert "reviewed value" in document and "onerror" in document and "{%" not in document
        assert page.evaluate("({local:localStorage.length,session:sessionStorage.length,cookie:document.cookie})")=={"local":0,"session":0,"cookie":""}
        assert not console
        browser.close()


def test_mocked_byok_frontend_and_key_lifecycle(live_servers):
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page()
        def relay(route):
            assert route.request.headers.get("x-provider-key")=="ephemeral-browser-canary"
            route.fulfill(status=200,content_type="application/json",body='{"request_id":"00000000-0000-4000-8000-000000000001","provider":"groq","model":"whisper-large-v3-turbo","text":"Mocked browser transcription.","language":{"requested":"en","detected":"en"},"audio":{"bytes":1644,"duration_seconds":0.1,"duration_source":"server_metadata"},"warnings":[]}')
        page.route("http://127.0.0.1:8000/v1/transcriptions",relay)
        page.goto("http://127.0.0.1:8080",wait_until="networkidle")
        page.locator("input[name=method][value=byok]").check();page.locator("#audio-file").set_input_files({"name":"sample.wav","mimeType":"audio/wav","buffer":wav_bytes()})
        page.locator("#provider-key").fill("ephemeral-browser-canary");page.locator("#relay-consent").check()
        page.locator("#transcribe").click();page.wait_for_function("document.querySelector('#transcript').value.includes('Mocked browser transcription')")
        assert page.locator("#provider-key").input_value()==""
        page.locator("#provider-key").fill("ephemeral-browser-canary");page.locator("#remove-key").click();assert page.locator("#provider-key").input_value()==""
        browser.close()


def test_mobile_reflow_and_link_safety(live_servers):
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={"width":320,"height":720})
        page.goto("http://127.0.0.1:8080",wait_until="networkidle")
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        for link in page.locator('a[target="_blank"]').all():assert set((link.get_attribute("rel")or"").split())>={"noopener","noreferrer"}
        browser.close()


def test_mocked_speech_results_are_text_only_and_stop_on_edit(live_servers):
    script="""
    class MockRecognition {
      constructor(){ window.mockRecognition=this; }
      start(){ queueMicrotask(()=>this.onstart && this.onstart()); }
      stop(){ queueMicrotask(()=>this.onend && this.onend()); }
    }
    window.SpeechRecognition=MockRecognition;
    """
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page();page.add_init_script(script)
        page.goto("http://127.0.0.1:8080",wait_until="networkidle")
        page.locator("#speech-start").click();page.wait_for_function("!document.querySelector('#speech-stop').disabled")
        page.evaluate("""() => {
          const interim=[{transcript:'interim words'}]; interim.isFinal=false;
          window.mockRecognition.onresult({resultIndex:0,results:[interim]});
        }""")
        assert page.locator("#interim").inner_text()=="interim words"
        page.evaluate("""() => {
          const final=[{transcript:'<img src=x onerror=alert(1)> final words'}]; final.isFinal=true;
          window.mockRecognition.onresult({resultIndex:0,results:[final]});
        }""")
        assert "<img src=x onerror=alert(1)> final words" in page.locator("#transcript").input_value()
        assert page.locator("#interim img").count()==0
        page.locator("#transcript").focus();page.wait_for_function("document.querySelector('#speech-stop').disabled")
        browser.close()
