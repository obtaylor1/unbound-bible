import os
import tempfile
from pathlib import Path
from fastapi import HTTPException, UploadFile
from mutagen import File as AudioFile
from mutagen import MutagenError


ALLOWED_AUDIO_TYPES = {'audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/x-m4a'}
ALLOWED_SUFFIXES = {'.mp3', '.wav', '.m4a'}


async def store_bounded_audio(upload: UploadFile, *, max_bytes: int, temp_dir: str | None = None) -> tuple[str, bytes]:
    suffix = Path(upload.filename or '').suffix.lower()
    if upload.content_type not in ALLOWED_AUDIO_TYPES or suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(415, detail={'code': 'unsupported_audio', 'message': 'Upload an MP3, WAV, or M4A audio file.'})
    path = None
    try:
        with tempfile.NamedTemporaryFile(prefix='unbound-sermon-', suffix=suffix, dir=temp_dir, delete=False) as target:
            path = target.name; total = 0
            while chunk := await upload.read(64 * 1024):
                total += len(chunk)
                if total > max_bytes: raise HTTPException(413, detail={'code': 'upload_too_large', 'message': f'Audio files may not exceed {max_bytes} bytes.'})
                target.write(chunk)
        return path, Path(path).read_bytes()
    except Exception:
        if path and os.path.exists(path): os.unlink(path)
        raise


def cleanup_upload(path: str | None) -> None:
    if path and os.path.exists(path): os.unlink(path)


def validate_audio_duration(path: str, max_seconds: int) -> float:
    try:
        metadata = AudioFile(path)
        if metadata is None or not getattr(metadata, 'info', None): raise ValueError('missing metadata')
        duration = float(metadata.info.length)
    except (MutagenError, ValueError, TypeError, AttributeError) as error:
        raise HTTPException(422, detail={'code': 'invalid_audio', 'message': 'The uploaded file is not readable audio.'}) from error
    if duration > max_seconds:
        raise HTTPException(413, detail={'code': 'audio_too_long', 'message': f'Audio may not exceed {max_seconds} seconds.'})
    return duration
