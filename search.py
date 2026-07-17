import os
import json
import numpy as np
from google import genai
from google.genai import types
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def cosine_similarity(v1, v2):
    """두 벡터 간의 코사인 유사도를 계산합니다."""
    a = np.array(v1)
    b = np.array(v2)
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[오류] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        print(".env 파일을 생성하여 GEMINI_API_KEY=your_api_key_here 형식으로 작성해 주세요.")
        return

    embeddings_path = "movies_embeddings.json"
    if not os.path.exists(embeddings_path):
        print(f"[오류] '{embeddings_path}' 파일이 존재하지 않습니다.")
        print("먼저 collect_data.py 및 embed_data.py를 실행하여 영화 정보 및 임베딩을 만들어주세요.")
        return

    # 임베딩 데이터 로드
    print("로컬 영화 데이터베이스를 로드하는 중...")
    with open(embeddings_path, "r", encoding="utf-8") as f:
        movies = json.load(f)
    print(f"총 {len(movies)}개의 영화 데이터를 로드했습니다.")

    client = genai.Client()

    print("\n" + "="*50)
    print(" 한국 영화 시맨틱 검색기 (Gemini + Local NumPy)")
    print(" - 종료하려면 'exit' 또는 'q'를 입력하세요.")
    print("="*50)

    while True:
        try:
            query = input("\n검색어를 입력하세요 (예: '송강호 출연 스릴러', '가족과 보기 좋은 눈물나는 영화'): ").strip()
            if not query:
                continue
            if query.lower() in ['exit', 'q', 'quit']:
                print("검색기를 종료합니다. 감사합니다.")
                break

            print(f"'{query}' 검색 중...")

            # 검색어 임베딩 생성 (Gemini API 호출)
            response = client.models.embed_content(
                model="gemini-embedding-2",
                contents=query
            )
            query_vector = response.embeddings[0].values

            # 로컬 코사인 유사도 계산
            results = []
            for movie in movies:
                similarity = cosine_similarity(query_vector, movie["embedding"])
                results.append({
                    "title": movie["title"],
                    "year": movie["year"],
                    "actors": movie["actors"],
                    "synopsis": movie["synopsis"],
                    "similarity": similarity
                })

            # 유사도가 높은 순으로 정렬 (내림차순)
            results.sort(key=lambda x: x["similarity"], reverse=True)

            # 상위 5개 결과 출력
            print(f"\n[검색 결과 - 가장 유사한 영화 Top 5]")
            print("-"*50)
            for idx, res in enumerate(results[:5], 1):
                actors_str = ", ".join(res["actors"])
                print(f"{idx}. {res['title']} ({res['year']}) - 유사도: {res['similarity']:.4f}")
                print(f"   출연배우: {actors_str}")
                print(f"   줄거리: {res['synopsis']}")
                print("-"*50)

        except KeyboardInterrupt:
            print("\n검색기를 종료합니다.")
            break
        except Exception as e:
            print(f"[오류 발생] 검색 중 에러가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
