from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import supabase
import google.generativeai as genai
import json
import os  # 🌟 os 모듈 추가

router = APIRouter()

# 🌟 API 키를 코드에서 지우고 환경변수에서 안전하게 불러오도록 수정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 기존 Pydantic 모델 ---
class WordItem(BaseModel):
    cn_term: str
    pinyin: str
    kr_term: str
    category_name: str

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

# --- 🌟 추가된 AI용 Pydantic 모델 ---
class AIGenerateItem(BaseModel):
    topic: str
    category_name: str

class TranslateItem(BaseModel):
    text: str
    mode: str # 'KR_TO_CN' (한->중) 또는 'CN_TO_KR' (중->한)

# JSON 파싱을 위한 헬퍼 함수
def clean_json_string(s: str) -> str:
    s = s.strip()
    if s.startswith("```json"): s = s[7:]
    elif s.startswith("```"): s = s[3:]
    if s.endswith("```"): s = s[:-3]
    return s.strip()

# --------------------------------------------------------
# 🤖 [추가된 기능 1: AI 단어 자동 생성기]
# --------------------------------------------------------
@router.post("/ai/generate-words")
def generate_ai_words(item: AIGenerateItem):
    prompt = f"""
    당신은 중국어 교육 전문가입니다. '{item.topic}'와(과) 관련된 실생활/전문 중국어 단어 5개를 만들어주세요.
    반드시 아래 JSON 배열 형식으로만 대답하고 다른 말은 절대 하지 마세요.
    [
        {{"cn_term": "단어", "pinyin": "병음", "kr_term": "한국어 뜻"}}
    ]
    """
    try:
        response = model.generate_content(prompt)
        cleaned_json = clean_json_string(response.text)
        word_list = json.loads(cleaned_json)
        
        # 카테고리 확인 및 생성
        cat_res = supabase.table("categories").select("id").eq("name", item.category_name).execute()
        if len(cat_res.data) == 0:
            new_cat = supabase.table("categories").insert({"name": item.category_name}).execute()
            category_id = new_cat.data[0]["id"]
        else:
            category_id = cat_res.data[0]["id"]
            
        # 생성된 단어들을 DB에 한 번에 넣기
        for w in word_list:
            supabase.table("words").insert({
                "category_id": category_id,
                "cn_term": w["cn_term"],
                "pinyin": w["pinyin"],
                "kr_term": w["kr_term"]
            }).execute()
            
        return {"message": f"AI가 {len(word_list)}개의 단어를 성공적으로 생성하고 추가했습니다!", "words": word_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 생성 실패: {str(e)}")

# --------------------------------------------------------
# 🤖 [추가된 기능 2: 고도화된 뉘앙스 번역기]
# --------------------------------------------------------
@router.post("/ai/translate")
def translate_text(item: TranslateItem):
    direction = "한국어를 중국어로" if item.mode == "KR_TO_CN" else "중국어를 한국어로"
    
    prompt = f"""
    당신은 한-중 커플의 소통을 돕는 통역사입니다.
    다음 문장을 {direction} 번역해주세요: "{item.text}"
    
    기계적인 직역을 피하고, 실제 연인이나 일상생활에서 쓰는 자연스럽고 부드러운 표현으로 다듬어주세요.
    반드시 아래 JSON 형식으로만 대답하고 다른 말은 절대 하지 마세요.
    {{
        "translated": "번역된 문장",
        "pinyin": "병음 (한국어로 번역하는 경우 생략 가능)",
        "nuance": "이 표현이 어떤 뉘앙스를 가지는지, 어떤 상황에서 쓰면 좋은지 한국어로 1~2줄 설명"
    }}
    """
    try:
        response = model.generate_content(prompt)
        cleaned_json = clean_json_string(response.text)
        result = json.loads(cleaned_json)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"번역 실패: {str(e)}")


# --------------------------------------------------------
# [기존 기능들 (유저, 단어, 잔디, 카테고리, 인터랙션)]
# --------------------------------------------------------
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
    words_res = supabase.table("words").select("id, cn_term, pinyin, kr_term, categories(name)").execute()
    stats_res = supabase.table("user_word_stats").select("word_id, wrong_count").eq("user_id", user_id).execute()
    stats_map = {s["word_id"]: s["wrong_count"] for s in stats_res.data}
    result = []
    for w in words_res.data:
        cat_name = w["categories"]["name"] if w.get("categories") else "기본"
        result.append({
            "id": w["id"], "term": w["cn_term"], "pinyin": w["pinyin"],
            "definition": w["kr_term"], "category": cat_name, "wrong_count": stats_map.get(w["id"], 0)
        })
    return result

@router.post("/words")
def add_word(item: WordItem):
    cat_res = supabase.table("categories").select("id").eq("name", item.category_name).execute()
    if len(cat_res.data) == 0:
        new_cat = supabase.table("categories").insert({"name": item.category_name}).execute()
        category_id = new_cat.data[0]["id"]
    else: category_id = cat_res.data[0]["id"]
    supabase.table("words").insert({"category_id": category_id, "cn_term": item.cn_term, "pinyin": item.pinyin, "kr_term": item.kr_term}).execute()
    return {"message": "단어가 성공적으로 추가되었습니다."}

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
    return {"message": "상대방에게 전송되었습니다!"}

@router.get("/interactions/{user_id}")
def get_interactions(user_id: int):
    res = supabase.table("couple_interactions").select("id, sender_id, action_type, is_read, words(id, cn_term, pinyin, kr_term, categories(name))").eq("receiver_id", user_id).eq("is_read", False).execute()
    return res.data

@router.put("/interactions/{interaction_id}/read")
def mark_interaction_read(interaction_id: int):
    supabase.table("couple_interactions").update({"is_read": True}).eq("id", interaction_id).execute()
    return {"message": "읽음 처리 완료"}