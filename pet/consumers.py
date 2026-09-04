import json

from channels.generic.websocket import AsyncWebsocketConsumer


class PetConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data is not None or not text_data or len(text_data) > 10_000:
            await self.close(code=4400)
            return
        try:
            data = json.loads(text_data)
        except (TypeError, json.JSONDecodeError):
            await self.send(text_data=json.dumps({"type": "pet.error", "error": "Invalid JSON payload."}))
            return
        if not isinstance(data, dict):
            await self.send(text_data=json.dumps({"type": "pet.error", "error": "Payload must be an object."}))
            return
        await self.send(text_data=json.dumps({"type": "pet.event", "data": data}))

    async def pet_event(self, event):
        await self.send(text_data=json.dumps(event))
