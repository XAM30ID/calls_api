from typing import Annotated

from fastapi import Depends

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

# Связь с базой данных
DATABASE_URL='postgresql+asyncpg://root:root@postgres:5432/test_calls'
engine = create_async_engine(DATABASE_URL)
new_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with new_session() as session:
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class Base(DeclarativeBase):
    pass

class CallModel(Base):
    '''
        Модель звонков
    '''
    __tablename__ = 'Calls'

    id = Column(Integer, primary_key=True, unique=True)
    caller = Column(String)
    reciver = Column(String)
    started_at = Column(DateTime)
    recording = relationship("RecordModel", back_populates="call", uselist=False, lazy='selectin')
    
class RecordModel(Base):
    '''
        Модель записей
    '''
    __tablename__ = 'Records'

    id = Column(Integer, primary_key=True, unique=True)
    filename = Column(String)
    duration = Column(Integer)
    transcription = Column(String)
    call_id = Column(Integer, ForeignKey("Calls.id"))
    call = relationship("CallModel", back_populates="recording", uselist=False, lazy='selectin')


async def setup_database():
    '''
        Функция созданя базы данных
    '''
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()