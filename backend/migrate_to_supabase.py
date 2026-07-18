import os
import json
import numpy as np
from dotenv import load_dotenv
from supabase import create_client, Client

# 스크립트 디렉토리 기준 .env 로드
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
METADATA_FILE = os.path.join(SCRIPT_DIR, "movies_metadata.json")
EMBEDDINGS_FILE = os.path.join(SCRIPT_DIR, "movies_embeddings.npy")

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[오류] .env 파일에 SUPABASE_URL 또는 SUPABASE_KEY가 설정되어 있지 않습니다.")
        return

    if not os.path.exists(METADATA_FILE) or not os.path.exists(EMBEDDINGS_FILE):
        print("[오류] 마이그레이션할 로컬 파일 데이터베이스(JSON, .npy)가 존재하지 않습니다.")
        return

    print("로컬 Supabase 클라이언트 초기화 중...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("기존 데이터 백업 정리 중 (movies 테이블 비우기)...")
    try:
        # id가 0보다 큰 모든 행 삭제 (전체 초기화)
        supabase.table("movies").delete().gt("id", 0).execute()
        print("기존 테이블 데이터가 정상 초기화되었습니다.")
    except Exception as e:
        print(f"[알림] 테이블 초기화 실패 (신규 테이블인 경우 생략 가능): {e}")

    # 로컬 파일 데이터 로드
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        movies = json.load(f)
    embeddings = np.load(EMBEDDINGS_FILE)

    if len(movies) != len(embeddings):
        print(f"[오류] 데이터 정합성 불일치: 메타데이터({len(movies)}개) vs 임베딩({len(embeddings)}개)")
        return

    print(f"로컬 파일로부터 총 {len(movies)}개의 영화 및 임베딩 로드 완료.")
    print("Supabase 데이터베이스 대량 적재(Bulk Insert) 준비 중...")

    records = []
    for idx, movie in enumerate(movies):
        # numpy float32 배열을 파이썬 float 리스트로 캐스팅 (pgvector 규격에 맞춤)
        vector_list = embeddings[idx].tolist()
        
        records.append({
            "title": movie["title"],
            "year": int(movie["year"]),
            "actors": movie["actors"],
            "synopsis": movie["synopsis"],
            "category": movie.get("category", "korean"),
            "embedding": vector_list
        })

    # 배치로 인서트 (300개 영화이므로 한 번에 전송 가능)
    try:
        print("데이터베이스 적재 시작...")
        response = supabase.table("movies").insert(records).execute()
        print(f"성공적으로 {len(response.data)}개의 영화 데이터가 로컬 Supabase DB에 적재되었습니다!")
    except Exception as e:
        print(f"[오류] 데이터베이스 적재 실패: {e}")

if __name__ == "__main__":
    main()
