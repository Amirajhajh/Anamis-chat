# chat/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from .models import Chat
from .models import Chat, Message 
from django import forms
from django.db.models import Q, Max
from django.contrib.auth.models import User
from .models import Group, Channel
from django.urls import path, reverse

User = get_user_model()



@login_required
def chat_list(request):
    user = request.user
    chats = Chat.objects.filter(
        Q(user1=user) | Q(user2=user)
    ).distinct() # distinct() برای جلوگیری از تکرار چت‌ها اگر کاربر هم user1 و هم user2 باشد (که نباید اتفاق بیفتد)

    chat_data = []
    for chat in chats:

        if chat.user1 == user:
            other_user = chat.user2
        else:
            other_user = chat.user1

        # --- اضافه کردن آخرین پیام ---
        # روش اول: اگر رابطه مستقیم 'messages' روی مدل Chat دارید
        # last_message = chat.messages.order_by('-created_at').first()

        # روش دوم: کوئری مستقیم (امن‌تر)
        try:
            last_message = Message.objects.filter(chat=chat).order_by('-created_at').first()
        except NameError: # اگر مدل Message تعریف نشده باشد
             last_message = None
        # -----------------------------

        # --- اضافه کردن اطلاعات پروفایل ---
        profile_pic_url = None
        try:
            # فرض می‌کنیم other_user مدل استاندارد Django User است و profile_picture دارد
            # اگر فیلد عکس پروفایل دارید (مثلا ImageField یا FileField)
            if hasattr(other_user, 'profile_picture') and other_user.profile_picture:
                profile_pic_url = other_user.profile_picture.url
            
            # اگر از مدل Profile جداگانه استفاده می‌کنید:
            # profile_info = Profile.objects.get(user=other_user)
            # if profile_info.profile_picture:
            #     profile_pic_url = profile_info.profile_picture.url

        except Exception as e:
            # در صورت بروز خطا (مثلا مدل Profile وجود ندارد یا فیلد نیست)
            print(f"Error getting profile picture for user {other_user.username}: {e}")
            profile_pic_url = None # اطمینان از None بودن در صورت خطا
        # ----------------------------------

        chat_data.append({
            'chat': chat,
            'other_user': other_user,
            'last_message': last_message,
            'other_user_profile_pic': profile_pic_url, # اضافه کردن URL عکس پروفایل
        })

    # مرتب‌سازی بر اساس آخرین پیام (اگر last_message وجود دارد)
    chat_data.sort(key=lambda x: x['last_message'].created_at if x['last_message'] else None, reverse=True)

    return render(request, 'chat/chat_list.html', {'chat_data': chat_data})

@login_required
def start_chat(request):
    if request.method == 'POST':
        username_to_chat = request.POST.get('username')

        if not username_to_chat:
            return render(request, 'chat/start_chat.html', {'error': 'نام کاربری را وارد کنید.'})

        try:
            other_user = get_object_or_404(User, username=username_to_chat)

            if other_user == request.user:
                return render(request, 'chat/start_chat.html', {'error': 'نمی‌توانید با خودتان چت کنید.'})

            existing_chat = Chat.objects.filter(
                (Q(user1=request.user) & Q(user2=other_user)) |
                (Q(user1=other_user) & Q(user2=request.user))
            ).first()

            if existing_chat:
                return redirect('chat:chat_detail', chat_id=existing_chat.id)
            else:
                new_chat = Chat.objects.create(user1=request.user, user2=other_user)
                return redirect('chat:chat_detail', chat_id=new_chat.id)

        except Exception as e:
            return render(request, 'chat/start_chat.html', {'error': f'خطایی رخ داد: {str(e)}'})

    return render(request, 'chat/start_chat.html')



class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']  # <-- اینجا رو به content تغییر بده

@login_required
def send_message(request, receiver_id):
    receiver = get_object_or_404(User, id=receiver_id)
    
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.receiver = receiver
            message.save()
            return redirect('chat:inbox', receiver_id=receiver_id)
    else:
        form = MessageForm()
        return render(request, 'chat/send_message.html', {'form': form, 'receiver': receiver})
    if request.method == 'POST':
        content = request.POST.get('content')
        file = request.FILES.get('file')  # دریافت فایل آپلود شده
        
        # ایجاد پیام جدید
        message = Message.objects.create(
            sender=request.user,
            receiver_id=receiver_id,
            content=content,
            file=file  # ذخیره فایل در دیتابیس
        )
        
        # ریدایرکت به صفحه چت
        return redirect('chat:chat_room', receiver_id=receiver_id)

@login_required
def chat_detail(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)

    # ۱. بررسی دسترسی
    if chat.user1 != request.user and chat.user2 != request.user:
        return redirect('chat:chat_list')

    # ۲. پیدا کردن کاربر مقابل (مخاطب)
    # اگر کاربر جاری user1 است، مخاطب user2 است و برعکس
    if chat.user1 == request.user:
        other_user = chat.user2
    else:
        other_user = chat.user1

    # ۳. دریافت پیام‌ها
    messages = Message.objects.filter(chat=chat).order_by('created_at')

    # ۴. اگر درخواست POST بود
    if request.method == 'POST':
        content_text = request.POST.get('content')
        uploaded_file = request.FILES.get('file')  # دریافت فایل آپلود شده

        # بررسی اینکه آیا حداقل یکی از این‌ها وجود دارد؟
        if content_text or uploaded_file:
            Message.objects.create(
                chat=chat,
                sender=request.user,
                content=content_text if content_text else '',  # اگر متنی نبود، خالی بذار
                file=uploaded_file  # فایل رو اینجا ذخیره کن
            )
        
        # رفرش لیست پیام‌ها بعد از ارسال
        messages = Message.objects.filter(chat=chat).order_by('created_at')
        
        # اگر از Ajax استفاده نمی‌کنی، این خط رو حذف کن و صفحه رفرش میشه
        # return redirect('chat:chat_detail', chat_id=chat.id)

    # ۵. رندر صفحه با ارسال اطلاعات کاربر مقابل
    return render(request, 'chat/chat_detail.html', {
        'chat': chat,
        'messages': messages,
        'other_user': other_user, # <-- این خط جدید هست
    })


    # ۵. رندر صفحه با ارسال اطلاعات کاربر مقابل
    return render(request, 'chat/chat_detail.html', {
        'chat': chat,
        'messages': messages,
        'other_user': other_user, # <-- این خط جدید هست
    })


@login_required
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id)

    # فقط فرستنده بتواند حذف کند
    if message.sender != request.user:
        return redirect('chat:chat_list')

    chat_id = message.chat.id
    message.delete()

    return redirect('chat:chat_detail', chat_id=chat_id)

def profile_detail(request, user_id):
    # پیدا کردن کاربر بر اساس ID ارسالی از لینک
    target_user = get_object_or_404(User, id=user_id)
    
    # ارسال کاربر مورد نظر به قالب
    return render(request, 'chat/profile_detail.html', {
        'user': target_user
    })


@login_required
def chat_list_view(request):
    user = request.user
    # آپدیت وضعیت آنلاین و آخرین بازدید کاربر جاری
    user.online_status = True
    user.last_seen = timezone.now()
    user.save(update_fields=['online_status', 'last_seen'])

    # پیدا کردن آخرین پیام هر چت
    last_messages = Message.objects.filter(
        chat=OuterRef('pk')
    ).order_by('-timestamp')

    # گرفتن لیست چت‌های کاربر با select_related برای بهینه‌سازی
    # این خط باعث میشه دیتای کاربر (User) همزمان با چت لود بشه و نیاز به کوئری اضافی نباشه
    user_chats = Chat.objects.filter(participants=user).select_related('participants').annotate(
        last_message_timestamp=Subquery(last_messages.values('timestamp')[:1]),
        last_message_content=Subquery(last_messages.values('content')[:1]),
        last_message_sender_username=Subquery(last_messages.values('sender__username')[:1])
    ).order_by('-last_message_timestamp')

    chats_with_profiles = []
    for chat in user_chats:
        other_user = chat.get_other_user(user)
        if other_user:
            chats_with_profiles.append({
                'chat': chat,
                'other_user': other_user, # حالا other_user یک آبجکت User هست
                'online_status': other_user.online_status,
                'last_seen': other_user.last_seen,
                'last_message': chat.last_message_content,
                'last_message_sender': chat.last_message_sender_username,
                'chat_url': f'/chat/{chat.id}/'
            })

    context = {
        'chats': chats_with_profiles,
    }
    return render(request, 'chat/chat_list.html', context)

def profile_detail_current(request):
    return render(request, 'chat/profile_detail.html', {'user': request.user})


# فرض می‌کنیم تابع create_group_view درست نام‌گذاری شده در urls.py
# و تابع dashboard_view هم درست نام‌گذاری شده.

# @login_required # اگر می‌خواهید فقط کاربران لاگین شده بتوانند گروه بسازند
def create_group_view(request):
    """نمایش فرم ساخت گروه جدید."""
    return render(request, 'chat/create_group.html')

# @login_required
def process_group_creation_view(request):
    """پردازش فرم ساخت گروه."""
    if request.method == 'POST':
        group_name = request.POST.get('group_name')
        if group_name:
            # ساخت گروه و تنظیم مالک (کاربر فعلی)
            new_group = Group.objects.create(name=group_name, owner=request.user)

            
            # اگر مدل شما M2M برای اعضا دارد، کاربر فعلی را هم اضافه کن
            new_group.members.add(request.user)

            # بعد از ساخت گروه، به صفحه جزئیات گروه جدید ریدایرکت کن
            # فرض می‌کنیم نام URL برای جزئیات گروه 'chat_detail' است و chat_id را می‌گیرد
            return redirect(reverse('chat:chat_detail', kwargs={'chat_id': new_group.id}))
            
    # اگر نام گروه خالی بود یا متد POST نبود، دوباره به فرم ساخت گروه برگرد
    # مطمئن شو که 'create_group' نام صحیح URL در urls.py است
    return redirect(reverse('chat:create_group')) 
    # ویوی جدید برای پردازش پیام

@login_required
def chat_detail_group(request, chat_id):
    group = get_object_or_404(Group, id=chat_id, members=request.user)
    chat_instance, created = Chat.objects.get_or_create(group=group)
    # دریافت پیام‌ها و مرتب‌سازی
    messages = chat_instance.messages.all().order_by('created_at')
    
    return render(request, 'chat/group_chat_detail.html', {
        'group': group,
        'chat_messages': messages,
    })

@login_required
def process_group_message(request, chat_id):
    if request.method == "POST":
        group = get_object_or_404(Group, id=chat_id, members=request.user)
        content = request.POST.get('content', '').strip()
        
        if content:
            chat_instance, _ = Chat.objects.get_or_create(group=group)
            Message.objects.create(
                chat=chat_instance,
                sender=request.user,
                content=content
            )
            
    return redirect('chat:chat_group', chat_id=chat_id)






def dashboard_view(request):
    """یک ویو نمایشی برای داشبورد (به جای some_success_url)."""
    groups = Group.objects.all()
    channels = Channel.objects.all()
    context = {'groups': groups, 'channels': channels}
    return render(request, 'chat/dashboard.html', context)
def add_group_member(request, group_id):
    # این فقط برای رفع خطای فعلی است
    group = get_object_or_404(Group, id=group_id)
    return render(request, 'chat/add_member.html', {'group': group})
