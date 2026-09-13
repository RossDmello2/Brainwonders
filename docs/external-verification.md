# External contract verification — 2026-09-12

Official documentation was reopened before integration.

| Contract | Current evidence | Implementation decision |
|---|---|---|
| Groq transcription | The official [speech-to-text documentation](https://console.groq.com/docs/speech-to-text) still lists `POST https://api.groq.com/openai/v1/audio/transcriptions`, models `whisper-large-v3-turbo` and `whisper-large-v3`, direct uploads for FLAC/MP3/MP4/MPEG/MPGA/M4A/OGG/WAV/WEBM, and plan-dependent pricing/limits. | Fixed endpoint and two-model allowlist retained. The app's 8 MiB bound is deliberately smaller. No URL-input support. |
| Mistral transcription | The official [audio endpoint reference](https://docs.mistral.ai/api/endpoint/audio/transcriptions) still lists `POST /v1/audio/transcriptions`, while the [current model card](https://docs.mistral.ai/models/voxtral-mini-transcribe-26-02) identifies pinned model `voxtral-mini-2602`. The [audio overview](https://docs.mistral.ai/studio/audio/overview) now says recordings up to three hours; the app retains a conservative 10-minute product bound. | Fixed endpoint and pinned model retained. Only the intersection formats from the specification are forwarded. |
| Render Free | Official [Free service documentation](https://render.com/docs/free) still offers Python web services, warns against production use, spins services down after 15 idle minutes, grants 750 workspace hours, uses ephemeral files, and can bill supplementary bandwidth if a payment method is present. | Experimental Free target retained. No periodic keepalive. Owner card state and hosted measurements remain release gates. |
| Render Python | The [Python version documentation](https://render.com/docs/python-version) gives 3.14.3 as the current default for new services and supports explicit version selection. | Pin tested Python 3.12.6 through `.python-version` and `PYTHON_VERSION`. This is a changed default since older snapshots. |
| Cloudflare Pages Free | Official [Pages limits](https://developers.cloudflare.com/pages/platform/limits/) show 500 builds/month, 20,000 static files and 25 MiB per asset. | Static frontend remains well below the documented limits. Account enrollment is unverified. |

Browser speech recognition remains a browser-managed compatibility feature. Its standard interface does not offer a reliable remote-only guarantee; the UI discloses that unresolved boundary. Provider privacy, plan eligibility, quotas and charges belong to each visitor's provider account and are not represented as universally free.
