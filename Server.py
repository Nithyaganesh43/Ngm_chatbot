import os
import json
import re
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import openai

# Load environment variables first
load_dotenv()

# Django imports and setup
import django
from django.conf import settings
from django.core.management import execute_from_command_line
from django.urls import path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from django.utils import timezone

# Configure Django settings BEFORE importing models
settings.configure(
    DEBUG=True,
    SECRET_KEY='ngmc_secret',
    ROOT_URLCONF=__name__,
    ALLOWED_HOSTS=['*'],
    INSTALLED_APPS=[
        'django.contrib.contenttypes',
        'django.contrib.auth',
        __name__,
    ],
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'db.sqlite3'}},
    TIME_ZONE='Asia/Kolkata',
)

# Setup Django
django.setup()

# Web scraping setup
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

all_links = {}

# 1. Exam Schedule
url = "https://coe.ngmc.ac.in/exam-schedule/"
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")
exam_links = {}
for a_tag in soup.find_all("a"):
    href = a_tag.get("href")
    if href and href.lower().endswith(".pdf"):
        if href.startswith("/"):
            href = f"https://coe.ngmc.ac.in{href}"
        file_name = os.path.basename(href)
        key_name = os.path.splitext(file_name)[0]
        exam_links[key_name] = href
all_links["exam_schedule"] = exam_links

# 2. Fee Structure
url = "https://www.ngmc.org/admissions/fee-structure/"
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")
fee_links = {}
for a_tag in soup.find_all("a"):
    href = a_tag.get("href")
    if href and href.lower().endswith(".pdf"):
        if href.startswith("/"):
            href = f"https://www.ngmc.org{href}"
        file_name = os.path.basename(href)
        key_name = os.path.splitext(file_name)[0]
        fee_links[key_name] = href
all_links["fee_structure"] = fee_links

# 3. Seating Arrangements
url = "https://coe.ngmc.ac.in/seating-arrangements/"
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")
seating_links = {}
for a_tag in soup.find_all("a"):
    if "open" in a_tag.text.lower():
        link = a_tag.get("href")
        if link:
            if link.startswith("/"):
                link = f"https://coe.ngmc.ac.in{link}"
            file_name = os.path.basename(link)
            key_name = os.path.splitext(file_name)[0]
            seating_links[key_name] = link
all_links["seating_arrangements"] = seating_links

# 4. Syllabus
url = "https://www.ngmc.org/syllabus-list-2/"
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")
syllabus_links = {}
for a_tag in soup.find_all("a"):
    if "open" in a_tag.text.lower():
        link = a_tag.get("href")
        if link:
            name_tag = a_tag.find_previous(lambda tag: tag.name in ["h3", "h4", "span", "strong"] and tag.text.strip())
            name = name_tag.text.strip() if name_tag else f"link_{len(syllabus_links)+1}"
            if link.startswith("/"):
                link = f"https://www.ngmc.org{link}"
            syllabus_links[name] = link
all_links["syllabus"] = syllabus_links

# Save everything to one JSON
with open("ngmc_college_links.json", "w", encoding="utf-8") as f:
    json.dump(all_links, f, indent=4, ensure_ascii=False)

print(f"Saved data: Exam({len(exam_links)}), Fees({len(fee_links)}), Seating({len(seating_links)}), Syllabus({len(syllabus_links)}) → ngmc_college_links.json")

# Staff management functions
def load_staff(file_path="staff.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {file_path} not found. Staff functions will return empty data.")
        return {}

def get_all_departments():
    staff_data = load_staff()
    return list(staff_data.keys())

def get_staff_of_department(department):
    staff_data = load_staff()
    return staff_data.get(department, [])

def get_department_of_staff(staff_name):
    staff_data = load_staff()
    for dept, members in staff_data.items():
        for member in members:
            if member["name"].lower() == staff_name.lower():
                return dept
    return None

def get_hod(department):
    staff_list = get_staff_of_department(department)
    for staff in staff_list:
        if "principal" in staff["designation"].lower() or "head" in staff["designation"].lower():
            return staff
    return staff_list[0] if staff_list else None

# Models - NOW DEFINED AFTER django.setup()
class Chat(models.Model):
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = __name__

class Conversation(models.Model):
    chat = models.ForeignKey(Chat, related_name='conversation', on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=[('user','user'),('AI','AI')])
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = __name__

# OpenAI setup
openai.api_key = os.environ.get("CHAT_GPT_API")

ENHANCED_SYSTEM_PROMPT = """
You are an intelligent AI assistant for Nallamuthu Gounder Mahalingam College (NGMC), Pollachi.
Provide accurate, helpful, and engaging information about the college.
Official site: https://www.ngmc.org

You have access to the following college information:
- Exam schedules and seating arrangements
- Fee structure details
- Syllabus information for various courses
- Staff and department information

Always be helpful, accurate, and maintain a professional yet friendly tone.
"""

# Helper functions
def call_chatgpt(messages):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=1200,
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return "I'm sorry, I'm having trouble processing your request right now. Please try again later."

def extract_json_from_response(resp):
    try:
        parsed = json.loads(resp)
        if parsed.get('reply') and parsed.get('title'):
            return parsed
    except:
        pass
    
    match = re.search(r'\{[\s\S]*"reply"[\s\S]*"title"[\s\S]*\}', resp)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass
    
    return {"reply": resp, "title": "NGMC Query Response"}

def validate_message(msg):
    if not msg: 
        return "Valid message is required"
    if len(msg) > 1000: 
        return "Message too long (max 1000 chars)"
    return None

def auth_required(func):
    def wrapper(request, *args, **kwargs):
        password = request.headers.get('x-api-key')
        if password != os.environ.get("PASSWORD"):
            return JsonResponse({"error":"Unauthorized"}, status=401)
        return func(request, *args, **kwargs)
    return wrapper

# Views
@csrf_exempt
@auth_required
def post_chat(request):
    if request.method != 'POST': 
        return JsonResponse({"error":"POST required"}, status=405)
    
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error":"Invalid JSON"}, status=400)
    
    user_message = body.get('message','').strip()
    err = validate_message(user_message)
    if err: 
        return JsonResponse({"error": err}, status=400)
    
    prompt = f"{ENHANCED_SYSTEM_PROMPT}\nUser Query: {user_message}\nOutput JSON with reply and title only"
    messages = [{"role":"system","content":prompt},{"role":"user","content":user_message}]
    gpt_resp = call_chatgpt(messages)
    parsed = extract_json_from_response(gpt_resp)
    
    chat = Chat.objects.create(title=parsed['title'])
    Conversation.objects.bulk_create([
        Conversation(chat=chat, role='user', message=user_message),
        Conversation(chat=chat, role='AI', message=parsed['reply'])
    ])
    return JsonResponse({"chatId":chat.id,"reply":parsed['reply'],"title":parsed['title']})

@csrf_exempt
@auth_required
def continue_chat(request, chat_id):
    if request.method != 'POST': 
        return JsonResponse({"error":"POST required"}, status=405)
    
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error":"Invalid JSON"}, status=400)
    
    user_message = body.get('message','').strip()
    err = validate_message(user_message)
    if err: 
        return JsonResponse({"error": err}, status=400)
    
    try: 
        chat = Chat.objects.get(id=chat_id)
    except Chat.DoesNotExist: 
        return JsonResponse({"error":"Chat not found"}, status=404)
    
    last_msgs = Conversation.objects.filter(chat=chat).order_by('-id')[:10]
    conv_history = [{"role":"assistant" if c.role=="AI" else "user","content":c.message} for c in last_msgs][::-1]
    conv_history.append({"role":"user","content":user_message})
    
    prompt = f"{ENHANCED_SYSTEM_PROMPT}\nUser Query: {user_message}\nOutput JSON with reply and title only"
    messages = [{"role":"system","content":prompt}] + conv_history
    gpt_resp = call_chatgpt(messages)
    parsed = extract_json_from_response(gpt_resp)
    
    chat.title = parsed['title']
    chat.save()
    Conversation.objects.bulk_create([
        Conversation(chat=chat, role='user', message=user_message),
        Conversation(chat=chat, role='AI', message=parsed['reply'])
    ])
    return JsonResponse({"chatId":chat.id,"reply":parsed['reply'],"title":parsed['title']})

@auth_required
def get_chats(request):
    chats = Chat.objects.all().order_by('-id').values('id','title','created_at')
    return JsonResponse(list(chats), safe=False)

@auth_required
def get_chat(request, chat_id):
    try: 
        chat = Chat.objects.get(id=chat_id)
    except Chat.DoesNotExist: 
        return JsonResponse({"error":"Chat not found"}, status=404)
    
    convs = chat.conversation.order_by('id').values('role','message','created_at')
    data = {"id":chat.id,"title":chat.title,"conversation":list(convs)}
    return JsonResponse(data)

@csrf_exempt
@auth_required
def delete_chat(request, chat_id):
    if request.method != 'DELETE':
        return JsonResponse({"error":"DELETE method required"}, status=405)
    
    try: 
        chat = Chat.objects.get(id=chat_id)
    except Chat.DoesNotExist: 
        return JsonResponse({"error":"Chat not found"}, status=404)
    
    chat.delete()
    return JsonResponse({"message":"Chat deleted successfully","deletedChatId":chat_id})

# URL patterns
urlpatterns = [
    path('PostChat', post_chat),
    path('PostChat/<int:chat_id>', continue_chat),
    path('GetChat', get_chats),
    path('GetChat/<int:chat_id>', get_chat),
    path('DeleteChat/<int:chat_id>', delete_chat),
]

if __name__ == '__main__':
    # Create migrations and apply them
    execute_from_command_line([__file__,'makemigrations',__name__])
    execute_from_command_line([__file__,'migrate'])
    
    # Configure and run the server
    from django.core.management.commands.runserver import Command as runserver
    runserver.default_addr = "0.0.0.0"
    runserver.default_port = os.environ.get("PORT","8000")
    execute_from_command_line([__file__,'runserver'])