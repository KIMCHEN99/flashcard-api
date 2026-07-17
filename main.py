from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # CORS 모듈 불러오기
from app.routes import router

app = FastAPI()

# --- CORS(보안 해제) 설정 추가 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 주소(Netlify 포함)에서 오는 요청 허용
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, PUT 등 모든 방식 허용
    allow_headers=["*"],
)
# ------------------------------

app.include_router(router)