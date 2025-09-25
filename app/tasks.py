import time
from random import randint

from mutagen.mp3 import MP3
from mutagen.wave import WAVE

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.celery_app import celery_app
from app.database import CallModel, RecordModel


@celery_app.task
def get_sound_duration(file_path: str, record_id: int):
    '''
        Функция определения и изменения длительности записи звонка
    '''
    # Проверка расширения файла
    if file_path.split('.')[-1] == 'mp3':
        audio = MP3(file_path)
    elif file_path.split('.')[-1] == 'wav':
        audio = WAVE(file_path)
    else:
        return 0

    duration_seconds = audio.info.length
    
    # Связь с базой данных
    DATABASE_URL='postgresql://root:root@postgres:5432/test_calls'
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Изменение длительности записи
    with SessionLocal() as session:
        record = session.query(RecordModel).filter(RecordModel.id == record_id).first()
        call = session.query(CallModel).filter(CallModel.id == record.call_id).first()
        record.duration = duration_seconds
        silences = []
        for _ in range(randint(4, 10)):
            silences.append(randint(1, int(duration_seconds)))
        silences.sort()
        silences_list = map(lambda x: str(x), silences)
        print('='* 100)
        print(silences_list)
        record.silences = ';'.join(silences_list)
        call.recording = record
        call.status = 'processing'
        session.commit()
    return duration_seconds


@celery_app.task
def get_sound_text(record_id):
    '''
        Функция изменения расшифровки записи звонка
    '''

    # Связь с базой данных
    DATABASE_URL='postgresql://root:root@postgres:5432/test_calls'
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    time.sleep(4)  # Симуляция расшифровки

    # Запись расшифровки
    with SessionLocal() as session:
        record = session.query(RecordModel).filter(RecordModel.id == record_id).first()
        call = session.query(CallModel).filter(CallModel.id == record.call_id).first()
        record.transcription = 'Detected speech fragment: Hello world!'
        call.recording = record
        call.status = 'ready'
        session.commit()
    return 'Detected speech fragment: Hello world!'