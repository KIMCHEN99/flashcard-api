import os
from dotenv import load_dotenv
from supabase import create_client, Client

# .env 파일 로드
load_dotenv()

# 환경 변수에서 URL과 KEY 가져오기
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

# Supabase 클라이언트 생성
supabase: Client = create_client(url, key)