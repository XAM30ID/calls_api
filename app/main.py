import os
from datetime import datetime

from fastapi import FastAPI, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from fastapi import HTTPException
from datetime import datetime, timedelta
import os
from urllib.parse import urlencode
import hmac
import hashlib

from .database import setup_database, CallModel, SessionDep, RecordModel
from .tasks import get_sound_duration, get_sound_text

app = FastAPI()

# Схемы записи и звонка для валидации
class RecordSchema(BaseModel):
    filename: str
    duration: int
    transcription: str

class CallSchema(BaseModel):
    caller: str
    reciver: str
    started_at: datetime
    
    class Config:
        from_attributes = True


@app.post('/setup_database', tags=['Настройка'], summary='Создание базы данных', description='Эндпоинт для создания или перезаписи базы данных')
async def setup_database_url():
    '''
        Создание базы данных
    '''
    await setup_database()
    return {'message': 'Tables created successful!'}


@app.get('/calls/{call_id}/', tags=['Звонки'], summary='Получение звнока', description='Эндпоинт для получения звонка по id')
async def get_call(call_id: int, session: SessionDep):
    '''
        Получение звонка по id
    '''
    query = select(CallModel).filter(CallModel.id == call_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


@app.get('/calls/by_phone/{phone_number}/', tags=['Звонки'], summary='Получение звнока', description='Эндпоинт для получения звонка по номеру')
async def get_call_by_phone(phone_number: str, session: SessionDep):
    '''
        Получение звонка по номеру
    '''
    query = select(CallModel).filter(CallModel.caller == phone_number or CallModel.reciver == phone_number)
    result = await session.execute(query)
    return result.scalars().all()


@app.post('/calls', tags=['Звонки'], summary='Создание звонка', description='Эндпоинт для создания звонка. Указывается исходящий номер, входящий номер и дата начала')
async def create_call(new_call: CallSchema, session: SessionDep):
    '''
        Создание звонка
    '''
    call = CallModel(
        caller=new_call.caller,
        reciver=new_call.reciver,
        started_at=new_call.started_at,
    )
    session.add(call)
    await session.commit()

    query = select(CallModel)
    result = await session.execute(query)
    return {'message': 'Call created successful!', "id": result.all()[-1][0].id}



@app.post("/calls/{call_id}/recording/", response_model=RecordSchema, tags=['Звонки'], summary='Создание записи звонка', description='Эндпоинт для создания записи звонка. Указывается id и на сервер загружается файл .mp3 или .wav')
async def record_call(call_id: int, file: UploadFile, session: SessionDep):
    '''
        Отправка записи на сервер и сохранение в БД
    '''

    # Проверка расширения
    if file.content_type.split('/')[0] != 'audio':
        return {'message': 'Content type must be audio'}
    
    # Создание объекта модели записи и сохранение
    query = select(CallModel).filter(CallModel.id == call_id)
    result = await session.execute(query)
    call = result.scalar_one_or_none()
    new_record = RecordModel(
        filename=f'rec{call.id}.{file.filename.split('.')[-1]}',
        duration=0,
        transcription='',
        call_id=call.id,
        call=call
    )
    session.add(new_record)
    call.recording = new_record
    await session.commit()
    
    os.makedirs(os.path.join('app', 'records'), exist_ok=True)
    # Сохранение файла на сервер
    file_path = os.path.join('app', 'records', f'rec{call.id}.{file.filename.split('.')[-1]}')
    with open(file_path, 'wb') as f:
        f.write(file.file.read())

    # Запуск задач на получение длительности и расшифровки записи через Celery
    get_sound_duration.delay(file_path=file_path, record_id=new_record.id)
    get_sound_text.delay(record_id=new_record.id)
    
    return new_record



SECRET_KEY = "test-secret-key-here"

@app.get("/calls/records/{record_id}/download-url", tags=['Записи'], summary='Получить URL для скачивания записи')
async def get_download_url(record_id: int, session: SessionDep, expires_in: int = 3600):
    """
    Генерирует presigned URL для скачивания записи.
    """
    # Находим запись в базе
    query = select(RecordModel).filter(RecordModel.id == record_id)
    result = await session.execute(query)
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    # Проверяем существование файла
    file_path = os.path.join('app', 'records', record.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    # Генерируем presigned URL
    presigned_url = generate_presigned_url(record_id, record.filename, expires_in)
    
    return {
        "record_id": record_id,
        "filename": record.filename,
        "download_url": presigned_url,
        "expires_at": (datetime.now() + timedelta(seconds=expires_in)).isoformat(),
        "expires_in_seconds": expires_in
    }


def generate_presigned_url(record_id: int, filename: str, expires_in: int) -> str:
    """Генерирует presigned URL с подписью"""
    # Время истечения срока действия
    expiration = int((datetime.now() + timedelta(seconds=expires_in)).timestamp())
    
    # Данные для подписи
    data_to_sign = f"{record_id}:{filename}:{expiration}"
    
    # Создаем подпись
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        data_to_sign.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Кодируем параметры
    params = {
        'record_id': record_id,
        'filename': filename,
        'expires': expiration,
        'signature': signature
    }
    
    # Возвращаем полный URL
    base_url = "http://localhost:8000"
    return f"{base_url}/download/record?{urlencode(params)}"