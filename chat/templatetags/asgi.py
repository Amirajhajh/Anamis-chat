import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
# دقت کنید: این ایمپورت مربوط به فایل routing شماست که باید ساخته باشید
# اگر هنوز فایل routings.py را نساخته‌اید، موقتاً این خط را کامنت کنید
try:
    import chat.routing 
except ImportError:
    chat = None

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Anamis.settings')

application = ProtocolTypeRouter({
    # این بخش درخواست‌های HTTP معمولی را مدیریت می‌کند
    "http": get_asgi_application(),

    # این بخش درخواست‌های WebSocket را مدیریت می‌کند
    "websocket": AuthMiddlewareStack(
        URLRouter(
            chat.get_application_routes() if chat else []
        )
    ),
})

