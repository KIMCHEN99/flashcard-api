from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import supabase
import google.generativeai as genai
import json
import os
import base64

router = APIRouter()

# 환경변수에서 API 키 불러오기
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
# 최신 모델 적용
model = genai.GenerativeModel('gemini-3.5-flash')

# --- Pydantic 모델 ---
class WordItem(BaseModel):
    cn_term: str
    pinyin: str
    kr_term: str
    category_name: str
    example_cn: str = ""  
    example_kr: str = ""  

class StudyLogItem(BaseModel):
    log_date: str

class CategoryItem(BaseModel):
    name: str
    icon: str = "📁"
    color_code: str = "#8B9DFF"

class InteractionItem(BaseModel):
    sender_id: int
    receiver_id: int
    action_type: str
    word_id: int

class AIGenerateItem(BaseModel):
    topic: str

class TranslateItem(BaseModel):
    text: str = ""
    image_base64: str = "" 

def clean_json_string(s: str) -> str:
    s = s.strip()
    if s.startswith("```json"): s = s[7:]
    elif s.startswith("```"): s = s[3:]
    if s.endswith("```"): s = s[:-3]
    return s.strip()

# --- AI 기능 ---
@router.post("/ai/generate-preview")
def generate_ai_preview(item: AIGenerateItem):
    prompt = f"""
    당신은 중국어 교육 전문가입니다. '{item.topic}'와(과) 관련된 실생활/전문 중국어 단어 5개를 만들어주세요.
    반드시 각 단어를 사용한 자연스러운 중국어 예문과 한국어 해석도 포함해야 합니다.
    반드시 아래 JSON 배열 형식으로만 대답하고 다른 말은 절대 하지 마세요.
    [
        {{"cn_term": "단어", "pinyin": "병음", "kr_term": "한국어 뜻", "example_cn": "중국어 예문", "example_kr": "예문 한국어 해석"}}
    ]
    """
    try:
        response = model.generate_content(prompt)
        cleaned_json = clean_json_string(response.text)
        word_list = json.loads(cleaned_json)
        return word_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 생성 실패: {str(e)}")

@router.post("/ai/translate")
def translate_text(item: TranslateItem):
    prompt = f"""
    당신은 한-중 커플의 소통을 돕는 통역사입니다.
    입력된 텍스트나 이미지를 분석하여, 한국어면 중국어로, 중국어면 한국어로 자동 번역해주세요.
    기계적인 직역을 피하고, 실제 연인이나 일상생활에서 쓰는 자연스럽고 부드러운 표현으로 다듬어주세요.
    
    입력된 텍스트: "{item.text}"
    
    반드시 아래 JSON 형식으로만 대답하고 다른 말은 절대 하지 마세요.
    {{
        "translated": "번역된 문장",
        "pinyin": "중국어로 번역된 경우 병음 표기 (한국어로 번역된 경우 빈 문자열)",
        "nuance": "이 표현이 어떤 뉘앙스를 가지는지, 어떤 상황에서 쓰면 좋은지 한국어로 1~2줄 설명"
    }}
    """
    try:
        if item.image_base64:
            img_data = base64.b64decode(item.image_base64)
            image_parts = [{"mime_type": "image/jpeg", "data": img_data}]
            response = model.generate_content([prompt, image_parts[0]])
        else:
            response = model.generate_content(prompt)
            
        cleaned_json = clean_json_string(response.text)
        result = json.loads(cleaned_json)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"번역 실패: {str(e)}")

# --- 기존 데이터 조회 및 추가 기능 ---
@router.get("/users")
def get_users():
    res = supabase.table("profiles").select("*").execute()
    return res.data

@router.get("/categories")
def get_categories():
    res = supabase.table("categories").select("*").execute()
    return res.data

@router.post("/categories")
def create_category(item: CategoryItem):
    existing = supabase.table("categories").select("id").eq("name", item.name).execute()
    if len(existing.data) > 0: return {"message": "이미 존재하는 카테고리입니다."}
    supabase.table("categories").insert({"name": item.name, "icon": item.icon, "color_code": item.color_code}).execute()
    return {"message": "새 카테고리가 생성되었습니다."}

@router.get("/words/{user_id}")
def get_words(user_id: int):
    words_res = supabase.table("words").select("id, cn_term, pinyin, kr_term, example_cn, example_kr, categories(name)").execute()
    stats_res = supabase.table("user_word_stats").select("word_id, wrong_count").eq("user_id", user_id).execute()
    stats_map = {s["word_id"]: s["wrong_count"] for s in stats_res.data}
    
    result = []
    for w in words_res.data:
        cat_name = w["categories"]["name"] if w.get("categories") else "기본"
        result.append({
            "id": w["id"], 
            "term": w["cn_term"], 
            "pinyin": w["pinyin"],
            "definition": w["kr_term"], 
            "example_cn": w.get("example_cn", ""),
            "example_kr": w.get("example_kr", ""),
            "category": cat_name, 
            "wrong_count": stats_map.get(w["id"], 0)
        })
    return result

@router.post("/words")
def add_word(item: WordItem):
    cat_res = supabase.table("categories").select("id").eq("name", item.category_name).execute()
    if len(cat_res.data) == 0:
        new_cat = supabase.table("categories").insert({"name": item.category_name}).execute()
        category_id = new_cat.data[0]["id"]
    else: category_id = cat_res.data[0]["id"]
    
    supabase.table("words").insert({
        "category_id": category_id, 
        "cn_term": item.cn_term, 
        "pinyin": item.pinyin, 
        "kr_term": item.kr_term,
        "example_cn": item.example_cn,
        "example_kr": item.example_kr
    }).execute()
    return {"message": "단어가 성공적으로 추가되었습니다."}

# 🌟 [신규] 카테고리 삭제 기능 (연결된 단어도 모두 삭제)
@router.delete("/categories/{category_id}")
def delete_category(category_id: int):
    try:
        words = supabase.table("words").select("id").eq("category_id", category_id).execute().data
        word_ids = [w["id"] for w in words]
        if word_ids:
            supabase.table("user_word_stats").delete().in_("word_id", word_ids).execute()
            supabase.table("couple_interactions").delete().in_("word_id", word_ids).execute()
            supabase.table("words").delete().eq("category_id", category_id).execute()
        supabase.table("categories").delete().eq("id", category_id).execute()
        return {"message": "카테고리가 삭제되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 🌟 [신규] 개별 단어 삭제 기능
@router.delete("/words/{word_id}")
def delete_word(word_id: int):
    try:
        supabase.table("user_word_stats").delete().eq("word_id", word_id).execute()
        supabase.table("couple_interactions").delete().eq("word_id", word_id).execute()
        supabase.table("words").delete().eq("id", word_id).execute()
        return {"message": "단어가 삭제되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/words/{word_id}/wrong/{user_id}")
def increment_wrong_count(word_id: int, user_id: int):
    existing = supabase.table("user_word_stats").select("*").eq("user_id", user_id).eq("word_id", word_id).execute()
    if len(existing.data) == 0: supabase.table("user_word_stats").insert({"user_id": user_id, "word_id": word_id, "wrong_count": 1}).execute()
    else: supabase.table("user_word_stats").update({"wrong_count": existing.data[0]["wrong_count"] + 1}).eq("user_id", user_id).eq("word_id", word_id).execute()
    return {"message": "오답이 기록되었습니다."}

@router.post("/study-logs/{user_id}")
def add_study_log(user_id: int, log: StudyLogItem):
    existing = supabase.table("study_logs").select("*").eq("user_id", user_id).eq("log_date", log.log_date).execute()
    if len(existing.data) == 0:
        supabase.table("study_logs").insert({"user_id": user_id, "log_date": log.log_date}).execute()
        return {"message": "오늘의 잔디가 심어졌습니다!"}
    return {"message": "오늘은 이미 학습을 완료했습니다."}

@router.get("/study-logs/couple/all")
def get_couple_study_logs():
    res = supabase.table("study_logs").select("user_id, log_date").execute()
    logs = {"1": [], "2": []}
    for item in res.data:
        uid = str(item["user_id"])
        if uid in logs: logs[uid].append(item["log_date"])
    return logs

@router.post("/interactions")
def send_interaction(item: InteractionItem):
    supabase.table("couple_interactions").insert({
        "sender_id": item.sender_id, "receiver_id": item.receiver_id, "action_type": item.action_type, "word_id": item.word_id
    }).execute()
    return {"message": "전송 완료"}

@router.get("/interactions/{user_id}")
def get_interactions(user_id: int):
    res = supabase.table("couple_interactions").select("id, sender_id, action_type, is_read, words(id, cn_term, pinyin, kr_term, categories(name))").eq("receiver_id", user_id).eq("is_read", False).execute()
    return res.data

@router.put("/interactions/{interaction_id}/read")
def mark_interaction_read(interaction_id: int):
    supabase.table("couple_interactions").update({"is_read": True}).eq("id", interaction_id).execute()
    return {"message": "읽음 처리 완료"}