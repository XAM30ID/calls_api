from mutagen.mp3 import MP3
from mutagen.wave import WAVE

audio = MP3("app\\records\\rec1.mp3")
duration_seconds = audio.info.length  # Продолжительность в секундах
duration_minutes = duration_seconds / 60

print(f"Продолжительность: {duration_seconds:.2f} сек. ({duration_minutes:.2f} мин.)")