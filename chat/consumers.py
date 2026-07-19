from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Chat, Message
import json
import datetime

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.chat_group_name = f'chat_{self.chat_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.chat_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.chat_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_text = data.get('message')
        
        if not message_text:
            return # Ignore empty messages

        # Get current user (assuming authentication is handled)
        # You might need to pass user info through the WebSocket connection or a token
        # For simplicity here, we'll assume we can get it (this is a simplification!)
        # In a real app, you'd likely use token auth or session cookies
        
        # Let's simulate getting the user for now (replace with actual auth logic)
        # In a real app, you'd get user from scope['user'] if AuthMiddlewareStack is used
        # For this example, we will simulate it. Replace 'anonymous user' with actual logic.
        sender_id = self.scope['user'].id if self.scope['user'].is_authenticated else None
        if not sender_id:
             await self.send(text_data=json.dumps({
                'error': 'User not authenticated'
            }))
             return
        
        current_chat_id = int(self.chat_id)
        
        # Save message to database
        message = await self.create_message(current_chat_id, sender_id, message_text)

        # Send message to room group
        await self.channel_layer.group_send(
            self.chat_group_name,
            {
                'type': 'chat_message',
                'message': message.content,
                'sender': message.sender.username, # Send username for display
                'timestamp': message.created_at.isoformat(), # Send timestamp
                'message_id': message.id, # Send message ID for potential future use
            }
        )

    # Receive message from room group
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event.get('sender', 'Unknown'), # Handle cases where sender might not be present
            'timestamp': event.get('timestamp', datetime.datetime.now().isoformat()),
            'message_id': event.get('message_id'),
        }))

    @database_sync_to_async
    def create_message(self, chat_id, sender_id, content):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            chat = Chat.objects.get(id=chat_id)
            sender = User.objects.get(id=sender_id)
            message = Message.objects.create(chat=chat, sender=sender, content=content)
            return message
        except Exception as e:
            print(f"Error creating message: {e}")
            return None
