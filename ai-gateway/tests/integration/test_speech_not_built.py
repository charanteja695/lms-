"""app/providers/speech.py: the STT/TTS routing contract exists but no provider is configured — see the module
docstring and README "Not built"."""


async def test_transcription_answers_not_configured(client, internal_headers):
    files = {"audio": ("clip.wav", b"RIFF....", "audio/wav")}
    response = await client.post("/api/v1/internal/transcriptions", files=files, headers=internal_headers)
    assert response.status_code == 503
    assert response.json()["code"] == "PROVIDER_NOT_CONFIGURED"


async def test_speech_answers_not_configured(client, internal_headers):
    response = await client.post("/api/v1/internal/speech", json={"text": "Hello there"}, headers=internal_headers)
    assert response.status_code == 503
    assert response.json()["code"] == "PROVIDER_NOT_CONFIGURED"


async def test_transcription_still_requires_the_internal_token(client):
    files = {"audio": ("clip.wav", b"RIFF....", "audio/wav")}
    response = await client.post("/api/v1/internal/transcriptions", files=files)
    assert response.status_code == 403
