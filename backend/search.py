import os
import json
import numpy as np
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

    metadata_path = "movies_metadata.json"
    embeddings_path = "movies_embeddings.npy"
    
    if not os.path.exists(metadata_path) or not os.path.exists(embeddings_path):
        print(f"[오류] 데이터베이스 파일이 존재하지 않습니다. 먼저 embed_data.py를 실행해주세요.")
        return

    # 임베딩 데이터 로드
    print("로컬 고속 바이너리 영화 데이터베이스 로드 중...")
    with open(metadata_path, "r", encoding="utf-8") as f:
        movies = json.load(f)
    embeddings = np.load(embeddings_path)
    print(f"총 {len(movies)}개의 영화 데이터를 로드했습니다. (임베딩 차원: {embeddings.shape[1]})")

    client = genai.Client()

    print("\n" + "="*50)
    print(" 영화 시맨틱 검색기 [고성능 바이너리 벡터 연산 버전]")
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

            # 검색어 임베딩 생성 (Gemini API 호출)
            response = client.models.embed_content(
                model="gemini-embedding-2",
                contents=query
            )
            query_vector = np.array(response.embeddings[0].values, dtype=np.float32)

            # 카테고리 필터링 적용
            filtered_indices = [i for i, m in enumerate(movies) if m.get("category", "korean") == category]
            if not filtered_indices:
                print("해당 카테고리에 데이터가 존재하지 않습니다.")
                continue

            category_metadata = [movies[i] for i in filtered_indices]
            category_embeddings = embeddings[filtered_indices]

            # 고속 벡터화 코사인 유사도 연산
            dot_products = np.dot(category_embeddings, query_vector)
            query_norm = np.linalg.norm(query_vector)
            movie_norms = np.linalg.norm(category_embeddings, axis=1)

            norms_prod = movie_norms * query_norm
            norms_prod[norms_prod == 0] = 1e-9

            similarities = dot_products / norms_prod

            # 결과 수집
            results = []
            for idx, sim in enumerate(similarities):
                movie = category_metadata[idx]
                results.append({
                    "title": movie["title"],
                    "year": movie["year"],
                    "actors": movie["actors"],
                    "synopsis": movie["synopsis"],
                    "similarity": float(sim)
                })

            # 유사도가 높은 순으로 정렬
            results.sort(key=lambda x: x["similarity"], reverse=True)

            # 상위 5개 결과 출력
            print(f"\n[검색 결과 - {category_labels[category]} Top 5]")
            print("-"*50)
            for idx, res in enumerate(results[:5], 1):
                actors_str = ", ".join(res["actors"])
                print(f"{idx}. {res['title']} ({res['year']}) - 유사도: {res['similarity'] * 100:.1f}%")
                print(f"   출연배우: {actors_str}")
                print(f"   줄거리: {res['synopsis']}")
                print("-"*50)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[오류 발생] 검색 중 에러가 발생했습니다: {e}")

    print("검색기를 종료합니다. 감사합니다.")

if __name__ == "__main__":
    main()
