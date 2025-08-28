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

try:
    mongo_client = MongoClient(os.environ.get("MONOGDB_CONNECTION_STRING"))
    mongo_client.admin.command('ping')
    db = mongo_client.ngmc_chatbot
    users_collection = db.users
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
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

# Configure Django settings (no corsheaders)
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
        MIDDLEWARE=[
            'django.middleware.common.CommonMiddleware',
        ],
        TIME_ZONE='Asia/Kolkata',
        USE_TZ=True,
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

django.setup()

# manual CORS helper
ALLOWED_ORIGINS = [
    "https://ngmchatbot.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

def add_cors_headers(request, response: HttpResponse) -> HttpResponse:
    origin = request.META.get("HTTP_ORIGIN")
    if origin in ALLOWED_ORIGINS:
        response["Access-Control-Allow-Origin"] = origin
    response["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key"
    response["Access-Control-Allow-Credentials"] = "true"
    return response

# Example route with manual CORS
@csrf_exempt
def check_auth(request):
    if request.method == "OPTIONS":
        resp = HttpResponse(status=204)
        return add_cors_headers(request, resp)
    data = {"status": "ok", "msg": "Auth check passed"}
    resp = JsonResponse(data)
    return add_cors_headers(request, resp)

urlpatterns = [
    path("checkAuth", check_auth),
]

# MongoDB Models (using simple classes instead of Django models)
class User:
    def __init__(self, userName, email, password, _id=None, created_at=None):
        self.id = _id
        self.userName = userName
        self.email = email
        self.password = password
        self.created_at = created_at or datetime.now()
    
    @classmethod
    def create(cls, userName, email, password):
        user_data = {
            'userName': userName,
            'email': email,
            'password': password,
            'created_at': datetime.now()
        }
        result = users_collection.insert_one(user_data)
        return cls(userName, email, password, result.inserted_id, user_data['created_at'])
    
    @classmethod
    def get_by_email(cls, email):
        user_data = users_collection.find_one({'email': email})
        if user_data:
            return cls(user_data['userName'], user_data['email'], user_data.get('password', ''), user_data['_id'], user_data['created_at'])
        return None
    
    @classmethod
    def get(cls, user_id):
        user_data = users_collection.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return cls(user_data['userName'], user_data['email'], user_data.get('password', ''), user_data['_id'], user_data['created_at'])
        return None

class Chat:
    def __init__(self, title, user_id, _id=None, created_at=None):
        self.id = _id
        self.title = title
        self.user_id = user_id
        self.created_at = created_at or datetime.now()
    
    @classmethod
    def create(cls, title, user_id=None):
        chat_data = {
            'title': title,
            'user_id': user_id,
            'created_at': datetime.now()
        }
        result = chats_collection.insert_one(chat_data)
        return cls(title, user_id, result.inserted_id, chat_data['created_at'])
    
    @classmethod
    def get(cls, chat_id):
        chat_data = chats_collection.find_one({'_id': ObjectId(chat_id)})
        if chat_data:
            return cls(chat_data['title'], chat_data.get('user_id'), chat_data['_id'], chat_data['created_at'])
        return None
    
    @classmethod
    def all(cls):
        chats = []
        for chat_data in chats_collection.find().sort('_id', -1):
            chats.append(cls(chat_data['title'], chat_data.get('user_id'), chat_data['_id'], chat_data['created_at']))
        return chats
    
    @classmethod
    def filter_by_user(cls, user_id):
        chats = []
        for chat_data in chats_collection.find({'user_id': user_id}).sort('_id', -1):
            chats.append(cls(chat_data['title'], chat_data['user_id'], chat_data['_id'], chat_data['created_at']))
        return chats
    
    def save(self):
        chats_collection.update_one(
            {'_id': self.id},
            {'$set': {'title': self.title, 'user_id': self.user_id, 'created_at': self.created_at}}
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
        users_collection.create_index("email", unique=True)
        users_collection.create_index("created_at")
        chats_collection.create_index("user_id")
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

for new line user \n use it.
for bold text use **text**.

ALWAYS output in JSON format with two keys: "reply" and "title". 

LIMITS:
- "reply" should be concise, ideally under 500 words.
- "title" should be a brief summary of the reply, ideally under 4 words.
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

def validate_user_data(userName: str, email: str, password: str = None) -> Optional[str]:
    if not userName or not userName.strip():
        return "Valid userName is required"
    if not email or not email.strip():
        return "Valid email is required"
    if len(userName.strip()) > 100:
        return "Username too long (max 100 chars)"
    if len(email.strip()) > 200:
        return "Email too long (max 200 chars)"
    # Basic email validation
    if "@" not in email or "." not in email.split("@")[-1]:
        return "Invalid email format"
    return None

def get_or_create_user(userName: str, email: str, password: str = None) -> User:
    """Get existing user by email or create new one"""
    existing_user = User.get_by_email(email)
    if existing_user:
        # Update userName and password if they're different
        update_fields = {}
        if existing_user.userName != userName:
            update_fields['userName'] = userName
            existing_user.userName = userName
        if password and existing_user.password != password:
            update_fields['password'] = password
            existing_user.password = password
        
        # Update database if there are changes
        if update_fields:
            users_collection.update_one(
                {'_id': existing_user.id},
                {'$set': update_fields}
            )
        return existing_user
    else:
        return User.create(userName, email, password or '')

def auth_required(func):
    def wrapper(request, *args, **kwargs):
        password = request.headers.get('x-api-key')
        if password != "Abkr212@ngmc":
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
    userName = body.get('userName','').strip()
    email = body.get('email','').strip()
    password = body.get('password','').strip()
    
    # Validate message
    err = validate_message(user_message)
    if err: 
        return JsonResponse({"error": err}, status=400)
    
    # Validate user data
    user_err = validate_user_data(userName, email, password)
    if user_err:
        return JsonResponse({"error": user_err}, status=400)
    
    # Get or create user
    try:
        user = get_or_create_user(userName, email, password)
    except Exception as e:
        print(f"User creation error: {e}")
        return JsonResponse({"error": "Failed to create/get user"}, status=500)
    
    prompt = f"{ENHANCED_SYSTEM_PROMPT}\nUser Query: {user_message}\nOutput JSON with reply and title only"
    messages = [{"role":"system","content":prompt},{"role":"user","content":user_message}]
    gpt_resp = call_chatgpt(messages)
    parsed = extract_json_from_response(gpt_resp)
    
    chat = Chat.create(title=parsed['title'], user_id=user.id)
    Conversation.bulk_create([
        Conversation(chat.id, 'user', user_message),
        Conversation(chat.id, 'AI', parsed['reply'])
    ])
    
    return JsonResponse({
        "chatId": str(chat.id),
        "reply": parsed['reply'],
        "title": parsed['title'],
        "userId": str(user.id)
    })

@csrf_exempt
@auth_required
def checkAuth(request): 
    return JsonResponse({ "status": "Authorized" })

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
    userName = body.get('userName','').strip()
    email = body.get('email','').strip()
    password = body.get('password','').strip()
    apikey = body.get('apikey','').strip()
    if apikey != "Abkr212@ngmc":
        return JsonResponse({"error":"Unauthorized"}, status=401)
    # Validate message
    err = validate_message(user_message)
    if err: 
        return JsonResponse({"error": err}, status=400)
    
    # Validate user data
    user_err = validate_user_data(userName, email, password)
    if user_err:
        return JsonResponse({"error": user_err}, status=400)
    
    try: 
        chat = Chat.get(chat_id)
        if not chat:
            return JsonResponse({"error":"Chat not found"}, status=404)
    except Exception: 
        return JsonResponse({"error":"Chat not found"}, status=404)
    
    # Get or create user
    try:
        user = get_or_create_user(userName, email, password)
    except Exception as e:
        print(f"User creation error: {e}")
        return JsonResponse({"error": "Failed to create/get user"}, status=500)
    
    # Check if user owns this chat (if chat has a user_id)
    if chat.user_id and str(chat.user_id) != str(user.id):
        return JsonResponse({"error": "Unauthorized to access this chat"}, status=403)
    
    # If chat doesn't have user_id (old chats), assign current user
    if not chat.user_id:
        chat.user_id = user.id
        chat.save()
    
    last_msgs = Conversation.filter_by_chat_last_n(chat, 10)
    conv_history = [{"role":"assistant" if c.role=="AI" else "user","content":c.message} for c in last_msgs][::-1]
    conv_history.append({"role":"user","content":user_message})
    
    prompt = f"{ENHANCED_SYSTEM_PROMPT}\nUser Query: {user_message}\nOutput JSON with reply only"
    messages = [{"role":"system","content":prompt}] + conv_history
    gpt_resp = call_chatgpt(messages)
    parsed = extract_json_from_response(gpt_resp)
     
    chat.save()
    Conversation.bulk_create([
        Conversation(chat.id, 'user', user_message),
        Conversation(chat.id, 'AI', parsed['reply'])
    ])
    
    return JsonResponse({
        "chatId": str(chat.id),
        "reply": parsed['reply'],
        "userId": str(user.id)
    })

@auth_required
def get_chats(request):
    # Get all chats with their conversations (backward compatibility)
    chats_data = []
    
    for chat in Chat.all():
        # Get all conversations for this chat
        conversations = Conversation.filter_by_chat(chat)
        
        chat_data = {
            'id': str(chat.id),
            'title': chat.title,
            'user_id': str(chat.user_id) if chat.user_id else None,
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

@csrf_exempt
@auth_required
def get_user_chats(request):
    if request.method != 'POST': 
        return JsonResponse({"error":"POST required"}, status=405)
    
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error":"Invalid JSON"}, status=400)
    
    email = body.get('email','').strip()
    
    if not email:
        return JsonResponse({"error": "Email is required"}, status=400)
    
    # Get user by email
    user = User.get_by_email(email)
    if not user:
        return JsonResponse({"error": "User not found"}, status=404)
    
    # Get user's chats
    user_chats = Chat.filter_by_user(user.id)
    chats_data = []
    
    for chat in user_chats:
        # Get all conversations for this chat
        conversations = Conversation.filter_by_chat(chat)
        
        chat_data = {
            'id': str(chat.id),
            'title': chat.title,
            'user_id': str(chat.user_id),
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
    
    return JsonResponse({
        "user": {
            "id": str(user.id),
            "userName": user.userName,
            "email": user.email
        },
        "chats": chats_data
    }, safe=False)

# URL patterns
urlpatterns = [
    path('checkAuth/', checkAuth),
    path('postchat/', post_chat),
    path('postchat/<str:chat_id>/', continue_chat),
    path('getchat/', get_chats),
    path('getuserchats/', get_user_chats),
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

def clean_json_to_txt(json_file:str, txt_file:str):
    with open(json_file,"r",encoding="utf-8") as f:
        content=f.read()
    # remove unwanted characters
    for ch in ['[',']','"','{','}',',']:
        content=content.replace(ch,'')
    # strip spaces and save
    with open(txt_file,"w",encoding="utf-8") as f:
        f.write(content.strip())
    print(f"Cleaned content saved to {txt_file}")

# usage
clean_json_to_txt("ngmc_college_links.json","links.txt")

if __name__ == '__main__': 
    from django.core.management.commands.runserver import Command as runserver
    runserver.default_addr = "0.0.0.0"
    runserver.default_port = os.environ.get("PORT", "8000")
    ensure_tables()
    print("Starting NGMC Chatbot Server...")
    print(f"Server will start at http://0.0.0.0:{runserver.default_port}")
    print("MongoDB initialized successfully!")
    
    execute_from_command_line([__file__, 'runserver'])