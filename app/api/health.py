from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request):
    settings = request.app.state.settings
    return {
        "service": "silero-openai-tts",
        "status": "ready",
        "server_playback": bool(settings.auto_play or settings.force_play),
    }
