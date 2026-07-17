from fastapi import APIRouter
from pydantic import BaseModel
from app.database import supabase

router = APIRouter()

class CardItem(BaseModel):
    term: str
    pinyin: str
    definition: str
    category: str

@router.get("/cards")
def get_cards():
    # flashcards 테이블에서 데이터 가져오기
    try:
        response = supabase.table("flashcards").select("*").execute()
        return response.data
    except Exception as e:
        return {"error": str(e)}
    
@router.post("/cards")
def add_card(card: CardItem):
    data = supabase.table("flashcards").insert({
        "term": card.term,
        "pinyin": card.pinyin,
        "definition": card.definition,
        "category": card.category
    }).execute()
    return {"message": "단어가 성공적으로 추가되었습니다!", "data": data.data}

@router.put("/cards/{card_id}/wrong")
def increment_wrong_count(card_id: int):
    # 1. 먼저 현재 단어의 데이터를 가져와 wrong_count 값을 확인합니다.
    response = supabase.table("flashcards").select("wrong_count").eq("id", card_id).execute()
    
    if len(response.data) == 0:
        return {"error": "단어를 찾을 수 없습니다."}
        
    current_count = response.data[0].get("wrong_count", 0)
    
    # 2. 오답 횟수를 1 증가시킵니다.
    new_count = current_count + 1
    
    # 3. 데이터베이스를 업데이트합니다.
    update_response = supabase.table("flashcards").update({"wrong_count": new_count}).eq("id", card_id).execute()
    
    return {"message": "오답 횟수가 증가되었습니다.", "new_count": new_count}