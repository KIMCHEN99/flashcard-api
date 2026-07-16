from fastapi import APIRouter
from app.database import supabase

router = APIRouter()

@router.get("/cards")
def get_cards():
    # flashcards 테이블에서 데이터 가져오기
    try:
        response = supabase.table("flashcards").select("*").execute()
        return response.data
    except Exception as e:
        return {"error": str(e)}