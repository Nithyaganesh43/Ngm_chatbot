import os
import json
import re
from typing import Dict, List, Optional
from dotenv import load_dotenv 
from openai import OpenAI
import requests
from bs4 import BeautifulSoup

# Load environment variables first
load_dotenv()

# Django imports and setup
import django
from django.conf import settings
from django.core.management import execute_from_command_line
from django.urls import path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import models, connection
from django.utils import timezone 

# Configure Django settings
if not settings.configured:
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
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': 'db.sqlite3'
            }
        },
        TIME_ZONE='Asia/Kolkata',
        USE_TZ=True,
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

django.setup()

# Models
class Chat(models.Model):
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = '__main__'
        db_table = 'chat'

class Conversation(models.Model):
    chat = models.ForeignKey(Chat, related_name='conversations', on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=[('user','user'),('AI','AI')])
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = '__main__'
        db_table = 'conversation'


def ensure_tables():
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL,
                created_at DATETIME NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role VARCHAR(10) NOT NULL,
                message TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chat(id) ON DELETE CASCADE
            )
        """)

ensure_tables()

# OpenAI client
client = OpenAI(api_key=os.environ.get("CHAT_GPT_API"))

def webScrabedData():
    current_dir=os.path.dirname(os.path.abspath(__file__))
    files=["staff.txt","links.txt"]
    contents=""
    for filename in files:
        filepath=os.path.join(current_dir,filename)
        if os.path.isfile(filepath):
            with open(filepath,"r",errors="ignore") as f:
                contents+=f.read()+"\n"
        else:
            contents+=f"[{filename} not found]\n"
    return contents.strip()


def get_last_5_conversations_as_string():
    conversations=Conversation.objects.all().order_by('-created_at')[:5]
    conversations=reversed(conversations)  # keep chronological order

    result=[]
    for conv in conversations:
        result.append(f"[{conv.role}] {conv.message}")
    return "\n".join(result)

ENHANCED_SYSTEM_PROMPT = """
You are an intelligent AI assistant for Nallamuthu Gounder Mahalingam College (NGMC), Pollachi.
Provide accurate, helpful, and engaging information about the college.
Official site: https://www.ngmc.org
 
Always be helpful, accurate, and maintain a professional yet friendly tone.

Dont repeat the same answer if asked multiple times.
 
Use the following web-scraped data for reference:
""" + webScrabedData() + """ 
and the last 5 conversations for context:
""" + get_last_5_conversations_as_string() + """
You may get 2 types of queries:
1. General queries about NGMC college, courses, admissions, facilities, etc.
for this you need to answer in a conversational manner.
2. Specific queries about exam schedules, fee structures, seating arrangements, syllabus, etc.
for this you need to  answer with simple and direct answers with relevant links from the provided data.
""" 
def call_chatgpt(messages: List[Dict]) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=1200,
            temperature=0.7
        )
        reply = response.choices[0].message.content.strip()

        # log usage cost in rupees
        usage = response.usage
        usd_prompt = (usage.prompt_tokens / 1000) * 0.03
        usd_completion = (usage.completion_tokens / 1000) * 0.06
        total_usd = usd_prompt + usd_completion
        rupees = round(total_usd * 84, 2)

        print(
            f"[LOG] Tokens used → prompt={usage.prompt_tokens}, "
            f"completion={usage.completion_tokens}, total={usage.total_tokens}, "
            f"cost≈₹{rupees}"
        )

        return reply
    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return "I'm sorry, I'm having trouble processing your request right now. Please try again later."


def extract_json_from_response(resp: str) -> Dict:
    try:
        parsed = json.loads(resp)
        if parsed.get('reply') and parsed.get('title'):
            return parsed
    except json.JSONDecodeError:
        pass
    
    match = re.search(r'\{[\s\S]*"reply"[\s\S]*"title"[\s\S]*\}', resp)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    return {"reply": resp, "title": "NGMC Query Response"}

def validate_message(msg: str) -> Optional[str]:
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
    
    prompt = f"{ENHANCED_SYSTEM_PROMPT}\nUser Query: {user_message}\nOutput JSON with reply a plain text alone"
    messages = [{"role":"system","content":prompt}] + conv_history
    gpt_resp = call_chatgpt(messages)
    parsed = extract_json_from_response(gpt_resp)
     
    chat.save()
    Conversation.objects.bulk_create([
        Conversation(chat=chat, role='user', message=user_message),
        Conversation(chat=chat, role='AI', message=parsed['reply'])
    ])
    return JsonResponse({"chatId":chat.id,"reply":parsed['reply'] })

@auth_required
def get_chats(request):
    # Get all chats with their conversations
    chats_data = []
    
    for chat in Chat.objects.all().order_by('-id'):
        # Get all conversations for this chat
        conversations = Conversation.objects.filter(chat=chat).order_by('created_at')
        
        chat_data = {
            'id': chat.id,
            'title': chat.title,
            'created_at': chat.created_at.isoformat(),
            'conversations': [
                {
                    'id': conv.id,
                    'role': conv.role,
                    'message': conv.message,
                    'created_at': conv.created_at.isoformat()
                }
                for conv in conversations
            ]
        }
        chats_data.append(chat_data)
    
    return JsonResponse(chats_data, safe=False)

# URL patterns
urlpatterns = [
    path('postchat/', post_chat),
    path('postchat/<int:chat_id>/', continue_chat),
    path('getchat/', get_chats),
]

 
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



if __name__ == '__main__': 
    from django.core.management.commands.runserver import Command as runserver
    runserver.default_addr = "0.0.0.0"
    runserver.default_port = os.environ.get("PORT", "8000")
    ensure_tables()
    print("Starting NGMC Chatbot Server...")
    print(f"Server will start at http://0.0.0.0:{runserver.default_port}")
    print("Database initialized successfully!")
    
    execute_from_command_line([__file__, 'runserver'])

