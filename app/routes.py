from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import supabase

router = APIRouter()

# --- Pydantic 모델 정의 ---
class WordItem(BaseModel):
    cn_term: str
    pinyin: str
    kr_term: str
    category_name: str

class StudyLogItem(BaseModel):
    log_date: str

# 🌟 추가됨: 카테고리 생성용 모델
class CategoryItem(BaseModel):
    name: str
    icon: str = "📁"
    color_code: str = "#8B9DFF"

# ----------------------------------------
# 1. 프로필 목록 불러오기
@router.get("/users")
def get_users():
    res = supabase.table("profiles").select("*").execute()
    return res.data

# 🌟 2. 카테고리 목록 불러오기 (새로 추가됨!)
@router.get("/categories")
def get_categories():
    res = supabase.table("categories").select("*").execute()
    return res.data

# 🌟 3. 새 카테고리 생성하기 (새로 추가됨!)
@router.post("/categories")
def create_category(item: CategoryItem):
    existing = supabase.table("categories").select("id").eq("name", item.name).execute()
    if len(existing.data) > 0:
        return {"message": "이미 존재하는 카테고리입니다."}
    
    supabase.table("categories").insert({
        "name": item.name,
        "icon": item.icon,
        "color_code": item.color_code
    }).execute()
    return {"message": "새 카테고리가 생성되었습니다."}

# 4. 특정 사용자의 단어 및 오답 횟수 불러오기
@router.get("/words/{user_id}")
def get_words(user_id: int):
    words_res = supabase.table("words").select("id, cn_term, pinyin, kr_term, categories(name)").execute()
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
            "category": cat_name,
            "wrong_count": stats_map.get(w["id"], 0)
        })
    return result

# 5. 새 단어 추가
@router.post("/words")
def add_word(item: WordItem):
    cat_res = supabase.table("categories").select("id").eq("name", item.category_name).execute()
    if len(cat_res.data) == 0:
        new_cat = supabase.table("categories").insert({"name": item.category_name}).execute()
        category_id = new_cat.data[0]["id"]
    else:
        category_id = cat_res.data[0]["id"]

    supabase.table("words").insert({
        "category_id": category_id,
        "cn_term": item.cn_term,
        "pinyin": item.pinyin,
        "kr_term": item.kr_term
    }).execute()
    return {"message": "단어가 성공적으로 추가되었습니다."}

# 6. 오답 횟수 증가
@router.put("/words/{word_id}/wrong/{user_id}")
def increment_wrong_count(word_id: int, user_id: int):
    existing = supabase.table("user_word_stats").select("*").eq("user_id", user_id).eq("word_id", word_id).execute()
    
    if len(existing.data) == 0:
        supabase.table("user_word_stats").insert({"user_id": user_id, "word_id": word_id, "wrong_count": 1}).execute()
    else:
        current_count = existing.data[0]["wrong_count"]
        supabase.table("user_word_stats").update({"wrong_count": current_count + 1}).eq("user_id", user_id).eq("word_id", word_id).execute()
        
    return {"message": "오답이 기록되었습니다."}

# 7. 잔디 심기
@router.post("/study-logs/{user_id}")
def add_study_log(user_id: int, log: StudyLogItem):
    existing = supabase.table("study_logs").select("*").eq("user_id", user_id).eq("log_date", log.log_date).execute()
    
    if len(existing.data) == 0:
        supabase.table("study_logs").insert({"user_id": user_id, "log_date": log.log_date}).execute()
        return {"message": "오늘의 잔디가 심어졌습니다!"}
    
    return {"message": "오늘은 이미 학습을 완료했습니다."}

# 8. 잔디 기록 불러오기
@router.get("/study-logs/{user_id}")
def get_study_logs(user_id: int):
    response = supabase.table("study_logs").select("log_date").eq("user_id", user_id).execute()
    return [item["log_date"] for item in response.data]