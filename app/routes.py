from fastapi import APIRouter
from pydantic import BaseModel
from app.database import supabase

router = APIRouter()

class CardItem(BaseModel):
    term: str
    pinyin: str
    definition: str

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
    data = supabase.table("cards").insert({
        "term": card.term,
        "pinyin": card.pinyin,
        "definition": card.definition
    }).execute()
    return {"message": "단어가 성공적으로 추가되었습니다!", "data": data.data}