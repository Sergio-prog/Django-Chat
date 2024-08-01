import json

from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

from room.models import Room, Message, Like


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        print(data)
        type = data["type"]
        if type == "message":
            message = data["message"]
            username = data["username"]
            room = data["room"]

            await self.save_message(username, room, message)

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat_message", "message": message, "username": username},
            )
        elif type == "like":
            message_id = data["message_id"]
            username = data["username"]
            liked = data["liked"]

            if liked:
                await self.add_like_to_message(username, message_id)
            else:
                await self.remove_like_from_message(username, message_id)

            likes_count = await self.get_likes_count(message_id)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "like_message",
                    "message_id": message_id,
                    "like_count": likes_count,
                    "liked": liked
                }
            )

    async def chat_message(self, event):
        message = event["message"]
        username = event["username"]

        # Send message to WebSocket
        await self.send(
            text_data=json.dumps({"message": message, "username": username})
        )

    async def like_message(self, event):
        message_id = event["message_id"]
        like_count = event["like_count"]
        liked = event["liked"]

        await self.send(
            text_data=json.dumps(
                {
                    "type": "like",
                    "message_id": message_id,
                    "like_count": like_count,
                    "liked": liked,
                }
            )
        )

    @sync_to_async
    def save_message(self, username, room, message):
        user = User.objects.get(username=username)
        room = Room.objects.get(slug=room)

        Message.objects.create(user=user, room=room, content=message)

    @sync_to_async
    def add_like_to_message(self, username, message_id):
        user = User.objects.get(username=username)
        message = Message.objects.get(id=message_id)

        if not Like.objects.filter(user=user, message=message).exists():
            Like.objects.create(user=user, message=message)


    @sync_to_async
    def remove_like_from_message(self, username, message_id):
        user = User.objects.get(username=username)
        message = Message.objects.get(id=message_id)

        Like.objects.filter(user=user, message=message).delete()


    @sync_to_async
    def get_likes_count(self, message_id):
        return Like.objects.filter(message_id=message_id).count()
