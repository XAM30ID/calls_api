import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

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
