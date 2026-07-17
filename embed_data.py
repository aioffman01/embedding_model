import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[오류] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        return

    input_path = "movies.json"
    output_path = "movies_embeddings.json"

    if not os.path.exists(input_path):
        print(f"[오류] '{input_path}' 파일이 존재하지 않습니다.")
        return

    # 영화 데이터 로드
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    movies = data.get("movies", [])
    if not movies:
        print("[오류] 영화 데이터가 비어 있습니다.")
        return

    # 기존 임베딩 정보 로드 (중복 연산 방지)
    existing_embeddings = {}
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                # 영화 제목을 키로 하는 임베딩 맵 생성
                existing_embeddings = {m["title"]: m["embedding"] for m in existing_data if "embedding" in m}
            print(f"기존 임베딩 로드 완료: {len(existing_embeddings)}개 영화")
        except Exception as e:
            print(f"[경고] 기존 임베딩 파일 읽기 실패 (새로 생성합니다): {e}")

    client = genai.Client()

    embedded_movies = []
    new_embeddings_count = 0

    print(f"총 {len(movies)}개의 영화 중 신규 데이터 임베딩 작업을 시작합니다...")

    for i, movie in enumerate(movies):
        title = movie["title"]
        category = movie.get("category", "korean")
        
        # 이미 임베딩이 존재하는 경우 재사용
        if title in existing_embeddings:
            embedded_movie = {
                "title": movie["title"],
                "year": movie["year"],
                "actors": movie["actors"],
                "synopsis": movie["synopsis"],
                "category": category, # 카테고리 정보 보존
                "embedding": existing_embeddings[title]
            }
            embedded_movies.append(embedded_movie)
        else:
            # 신규 임베딩 생성
            print(f"[{i+1}/{len(movies)}] 신규 영화 '{title}' 임베딩 생성 중...")
            actors_str = ", ".join(movie["actors"])
            doc = f"제목: {movie['title']}\n개봉년도: {movie['year']}년\n출연배우: actors_str\n줄거리: {movie['synopsis']}"
            
            try:
                response = client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=doc
                )
                vector = response.embeddings[0].values
                
                embedded_movie = {
                    "title": movie["title"],
                    "year": movie["year"],
                    "actors": movie["actors"],
                    "synopsis": movie["synopsis"],
                    "category": category, # 카테고리 정보 보존
                    "embedding": vector
                }
                embedded_movies.append(embedded_movie)
                new_embeddings_count += 1
            except Exception as e:
                print(f"[오류] '{title}' 임베딩 생성 중 실패: {e}")

    # 결과 저장
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(embedded_movies, f, ensure_ascii=False, indent=4)

    print(f"\n작업 완료! 신규 추가된 임베딩: {new_embeddings_count}개")
    print(f"최종 임베딩 데이터베이스 크기: {len(embedded_movies)}개")

if __name__ == "__main__":
    main()
