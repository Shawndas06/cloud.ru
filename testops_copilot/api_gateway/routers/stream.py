"""
Роутер для SSE streaming
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from uuid import UUID
import json
import asyncio
from typing import AsyncGenerator

from shared.utils.redis_client import redis_client
from shared.utils.database import SessionLocal
from shared.models.database import Request

router = APIRouter(prefix="/stream", tags=["Streaming"])


async def event_generator(request_id: UUID) -> AsyncGenerator[str, None]:
    """Генератор событий для SSE"""
    channel = f"request:{request_id}"
    
    # Проверка что request существует
    from shared.utils.database import SessionLocal
    db = SessionLocal()
    try:
        request = db.query(Request).filter(Request.request_id == request_id).first()
        if not request:
            yield f"event: error\ndata: {json.dumps({'error': 'Request not found'})}\n\n"
            return
    finally:
        db.close()
    
    # Подписка на канал через async Redis
    pubsub, redis_conn = await redis_client.subscribe_channel_async(channel)
    
    last_heartbeat = asyncio.get_event_loop().time()
    
    try:
        while True:
            # Получение сообщения из Redis Pub/Sub (неблокирующий)
            try:
                message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=1.0)
                
                if message and message['type'] == 'message':
                    data = json.loads(message['data'])
                    
                    if data.get('step') == 'completed':
                        yield f"event: completed\ndata: {json.dumps(data)}\n\n"
                        break
                    elif data.get('error'):
                        yield f"event: error\ndata: {json.dumps(data)}\n\n"
                        break
                    else:
                        yield f"event: progress\ndata: {json.dumps(data)}\n\n"
            except asyncio.TimeoutError:
                pass
            
            # Heartbeat каждые 30 секунд
            current_time = asyncio.get_event_loop().time()
            if current_time - last_heartbeat >= 30:
                yield f":heartbeat\n\n"
                last_heartbeat = current_time
            
            await asyncio.sleep(0.1)
    
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await redis_conn.close()




@router.get("/{request_id}")
async def stream_events(request_id: UUID):
    """
    SSE stream для real-time обновлений
    
    Устанавливает SSE соединение для получения обновлений о прогрессе выполнения задачи
    """
    # Проверка существования request
    from shared.utils.database import SessionLocal
    db = SessionLocal()
    try:
        request = db.query(Request).filter(Request.request_id == request_id).first()
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Request with ID {request_id} not found"
            )
    finally:
        db.close()
    
    return EventSourceResponse(event_generator(request_id))

