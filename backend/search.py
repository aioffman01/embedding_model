import os
from google import genai
from dotenv import load_dotenv
from supabase import create_client, Client

# 스크립트 디렉토리 획득
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[오류] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        return

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        print("[오류] Supabase 접속 정보(SUPABASE_URL, SUPABASE_KEY)가 설정되지 않았습니다.")
        return

    # Supabase 클라이언트 초기화
    print("로컬 Supabase 데이터베이스 연결 중...")
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        # 연결 확인차 간단한 쿼리 테스트 (count)
        res = supabase.table("movies").select("id", count="exact").limit(1).execute()
        count = res.count
        print(f"연동 성공! 현재 데이터베이스에 총 {count}개의 영화가 등록되어 있습니다.")
    except Exception as e:
        print(f"[오류] Supabase DB 연결에 실패했습니다: {e}")
        return

    client = genai.Client()

    print("\n" + "="*50)
    print(" 영화 시맨틱 검색기 [로컬 Supabase & pgvector 버전]")
    print(" - 종료하려면 'exit' 또는 'q'를 입력하세요.")
    print("="*50)

    category_labels = {
        "korean": "한국 영화",
        "foreign": "해외 영화",
        "anime": "일본 애니메이션"
    }

    while True:
        try:
            # 카테고리 선택
            print("\n검색할 카테고리를 선택하세요:")
            print("1. 한국 영화  2. 해외 영화  3. 일본 애니메이션  (종료: q)")
            cat_choice = input("선택 (1~3): ").strip()
            
            if cat_choice.lower() in ['q', 'exit', 'quit']:
                break
                
            category_map = {"1": "korean", "2": "foreign", "3": "anime"}
            category = category_map.get(cat_choice)
            if not category:
                print("[경고] 올바른 번호를 입력하세요.")
                continue

            query = input(f"\n[{category_labels[category]}] 검색어를 입력하세요: ").strip()
            if not query:
                continue
            if query.lower() in ['exit', 'q', 'quit']:
                break

            print(f"'{query}' 검색 중...")

            # 1. 검색어 임베딩 생성 (Gemini API 호출)
            response = client.models.embed_content(
                model="gemini-embedding-2",
                contents=query
            )
            query_vector = response.embeddings[0].values

            # 2. Supabase RPC 함수 호출하여 DB 단에서 코사인 유사도 검색 수행
            res = supabase.rpc("match_movies", {
                "query_embedding": query_vector,
                "match_threshold": 0.0,
                "match_count": 5, # CLI 검색기는 5개 출력
                "filter_category": category
            }).execute()

            results = res.data

            # 결과 출력
            if not results:
                print("유사한 영화를 찾지 못했습니다.")
                continue

            print(f"\n[검색 결과 - {category_labels[category]} Top {len(results)}]")
            print("-"*50)
            for idx, movie in enumerate(results, 1):
                actors_str = ", ".join(movie["actors"])
                print(f"{idx}. {movie['title']} ({movie['year']}) - 유사도: {movie['similarity'] * 100:.1f}%")
                print(f"   출연배우: {actors_str}")
                print(f"   줄거리: {movie['synopsis']}")
                print("-"*50)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[오류 발생] 검색 중 에러가 발생했습니다: {e}")

    print("검색기를 종료합니다. 감사합니다.")

if __name__ == "__main__":
    main()
