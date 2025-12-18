from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List
import json
from backend.app.models.database import ChatMessage, User, get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatManager:
    def __init__(self):
        # room_id -> list of websockets
        self.active_rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_rooms:
            self.active_rooms[room_id] = []
        self.active_rooms[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_rooms:
            self.active_rooms[room_id].remove(websocket)

    async def send_to_room(self, message: dict, room_id: str):
        if room_id in self.active_rooms:
            for connection in self.active_rooms[room_id]:
                await connection.send_json(message)


manager = ChatManager()


@router.websocket("/ws/{room_user_id}")
async def chat_endpoint(
        websocket: WebSocket,
        room_user_id: str,
        token: str,  # Trimis ca query param
        db: Session = Depends(get_db)
):
    # 1. Validare Token manuală (WebSockets nu suportă headere standard ușor)
    from backend.app.core.security import verify_token
    payload = verify_token(token)
    if not payload:
        await websocket.close(code=1008)
        return

    current_user_id = payload.get("sub")
    user = db.query(User).filter(User.id == current_user_id).first()

    # Restricție: Userii normali pot intra doar în camera lor proprie
    # Adminii pot intra în orice room_user_id
    if user.role != "admin" and str(user.id) != room_user_id:
        await websocket.close(code=1008)
        return

    room_id = f"user_{room_user_id}"
    await manager.connect(websocket, room_id)

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Salvare în baza de date
            new_msg = ChatMessage(
                room_id=room_id,
                user_id=user.id,
                message=message_data["text"],
                is_admin=(user.role == "admin")
            )
            db.add(new_msg)
            db.commit()

            # Broadcast în cameră
            await manager.send_to_room({
                "id": str(new_msg.id),
                "user_id": str(user.id),
                "name": f"{user.first_name} {user.last_name}",
                "text": message_data["text"],
                "is_admin": new_msg.is_admin,
                "created_at": new_msg.created_at.isoformat()
            }, room_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)