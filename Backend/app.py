import os
import json
import re
from typing import Dict, List, Optional
from dotenv import load_dotenv 
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime

# Load environment variables first
load_dotenv()
#env have MONGODB_CONNECTION_STRING , CHAT_GPT_API, PASSWORD

try:
    mongo_client = MongoClient(os.environ.get("MONOGDB_CONNECTION_STRING"))
    # Test the connection
    mongo_client.admin.command('ping')
    db = mongo_client.ngmc_chatbot
    chats_collection = db.chats
    conversations_collection = db.conversations
    print("✅ MongoDB connection successful!")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    print("Please ensure MongoDB is running or check your MONGODB_CONNECTION_STRING")
    exit(1)

# Django imports and setup
import django
from django.conf import settings
from django.core.management import execute_from_command_line
from django.urls import path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
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
        TIME_ZONE='Asia/Kolkata',
        USE_TZ=True,
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

django.setup()

# MongoDB Models (using simple classes instead of Django models)
class Chat:
    def __init__(self, title, _id=None, created_at=None):
        self.id = _id
        self.title = title
        self.created_at = created_at or datetime.now()
    
    @classmethod
    def create(cls, title):
        chat_data = {
            'title': title,
            'created_at': datetime.now()
        }
        result = chats_collection.insert_one(chat_data)
        return cls(title, result.inserted_id, chat_data['created_at'])
    
    @classmethod
    def get(cls, chat_id):
        chat_data = chats_collection.find_one({'_id': ObjectId(chat_id)})
        if chat_data:
            return cls(chat_data['title'], chat_data['_id'], chat_data['created_at'])
        return None
    
    @classmethod
    def all(cls):
        chats = []
        for chat_data in chats_collection.find().sort('_id', -1):
            chats.append(cls(chat_data['title'], chat_data['_id'], chat_data['created_at']))
        return chats
    
    def save(self):
        chats_collection.update_one(
            {'_id': self.id},
            {'$set': {'title': self.title, 'created_at': self.created_at}}
        )

class Conversation:
    def __init__(self, chat_id, role, message, _id=None, created_at=None):
        self.id = _id
        self.chat_id = chat_id
        self.role = role
        self.message = message
        self.created_at = created_at or datetime.now()
    
    @classmethod
    def bulk_create(cls, conversations):
        docs = []
        for conv in conversations:
            docs.append({
                'chat_id': conv.chat_id,
                'role': conv.role,
                'message': conv.message,
                'created_at': conv.created_at
            })
        conversations_collection.insert_many(docs)
    
    @classmethod
    def filter_by_chat(cls, chat):
        conversations = []
        for conv_data in conversations_collection.find({'chat_id': chat.id}).sort('created_at', 1):
            conversations.append(cls(
                conv_data['chat_id'],
                conv_data['role'],
                conv_data['message'],
                conv_data['_id'],
                conv_data['created_at']
            ))
        return conversations
    
    @classmethod
    def filter_by_chat_last_n(cls, chat, n):
        conversations = []
        for conv_data in conversations_collection.find({'chat_id': chat.id}).sort('_id', -1).limit(n):
            conversations.append(cls(
                conv_data['chat_id'],
                conv_data['role'],
                conv_data['message'],
                conv_data['_id'],
                conv_data['created_at']
            ))
        return conversations
    
    @classmethod
    def all(cls):
        conversations = []
        for conv_data in conversations_collection.find().sort('created_at', -1):
            conversations.append(cls(
                conv_data['chat_id'],
                conv_data['role'],
                conv_data['message'],
                conv_data['_id'],
                conv_data['created_at']
            ))
        return conversations

def ensure_tables():
    # MongoDB doesn't need table creation, but we can create indexes for performance
    try:
        chats_collection.create_index("created_at")
        conversations_collection.create_index([("chat_id", 1), ("created_at", 1)])
        print("MongoDB indexes created successfully!")
    except Exception as e:
        print(f"Index creation info: {e}")

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
    conversations = Conversation.all()[:5]
    conversations = reversed(conversations)  # keep chronological order

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
    
    chat = Chat.create(title=parsed['title'])
    Conversation.bulk_create([
        Conversation(chat.id, 'user', user_message),
        Conversation(chat.id, 'AI', parsed['reply'])
    ])
    return JsonResponse({"chatId":str(chat.id),"reply":parsed['reply'],"title":parsed['title']})

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
        chat = Chat.get(chat_id)
        if not chat:
            return JsonResponse({"error":"Chat not found"}, status=404)
    except Exception: 
        return JsonResponse({"error":"Chat not found"}, status=404)
    
    last_msgs = Conversation.filter_by_chat_last_n(chat, 10)
    conv_history = [{"role":"assistant" if c.role=="AI" else "user","content":c.message} for c in last_msgs][::-1]
    conv_history.append({"role":"user","content":user_message})
    
    prompt = f"{ENHANCED_SYSTEM_PROMPT}\nUser Query: {user_message}\nOutput JSON with reply a plain text alone"
    messages = [{"role":"system","content":prompt}] + conv_history
    gpt_resp = call_chatgpt(messages)
    parsed = extract_json_from_response(gpt_resp)
     
    chat.save()
    Conversation.bulk_create([
        Conversation(chat.id, 'user', user_message),
        Conversation(chat.id, 'AI', parsed['reply'])
    ])
    return JsonResponse({"chatId":str(chat.id),"reply":parsed['reply'] })

@auth_required
def get_chats(request):
    # Get all chats with their conversations
    chats_data = []
    
    for chat in Chat.all():
        # Get all conversations for this chat
        conversations = Conversation.filter_by_chat(chat)
        
        chat_data = {
            'id': str(chat.id),
            'title': chat.title,
            'created_at': chat.created_at.isoformat(),
            'conversations': [
                {
                    'id': str(conv.id),
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
    path('postchat/<str:chat_id>/', continue_chat),
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
    print("MongoDB initialized successfully!")
    
    execute_from_command_line([__file__, 'runserver'])