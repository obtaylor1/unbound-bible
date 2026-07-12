from fastapi import APIRouter, Depends, File, Request, UploadFile
from app.ai.factory import create_transcription_provider
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.security.rate_limits import enforce_rate_limit
from app.security.uploads import cleanup_upload, store_bounded_audio, validate_audio_duration


router = APIRouter(prefix='/analyze', tags=['sermon analysis'])


@router.post('/sermon', dependencies=[Depends(enforce_rate_limit('sermon', 'sermon_rate_limit', 3600))])
async def analyze_sermon(request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user)):
    path = None
    try:
        path, audio = await store_bounded_audio(file, max_bytes=request.app.state.settings.upload_max_bytes, temp_dir=request.app.state.settings.upload_temp_dir)
        duration = validate_audio_duration(path, request.app.state.settings.upload_max_duration_seconds)
        provider = create_transcription_provider(request.app.state.settings.ai_transcription_provider, request.app.state.settings)
        transcript = await provider.transcribe(audio, file.filename or 'sermon.mp3')
        return {'title': PathName(file.filename), 'speaker': user.username, 'duration': duration, 'transcript': transcript, 'summary': {'main_theme': 'Transcription complete. Configure grounded sermon analysis for claim-level review.', 'key_points': []}, 'claims': [], 'accuracy_score': 0, 'provider': provider.name, 'is_demo': provider.name == 'demo'}
    finally:
        cleanup_upload(path)


def PathName(filename: str | None) -> str:
    from pathlib import Path
    return Path(filename or 'Untitled sermon').stem
