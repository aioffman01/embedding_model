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

    input_path = "movies.json"
    metadata_output_path = "movies_metadata.json"
    embeddings_output_path = "movies_embeddings.npy"

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
    if os.path.exists(metadata_output_path) and os.path.exists(embeddings_output_path):
        try:
            with open(metadata_output_path, "r", encoding="utf-8") as f:
                existing_metadata = json.load(f)
            
            existing_vectors = np.load(embeddings_output_path)
            
            # 영화 제목과 벡터를 매핑
            if len(existing_metadata) == len(existing_vectors):
                existing_embeddings = {
                    existing_metadata[i]["title"]: existing_vectors[i] 
                    for i in range(len(existing_metadata))
                }
                print(f"기존 임베딩 로드 완료: {len(existing_embeddings)}개 영화")
            else:
                print("[경고] 메타데이터 수와 임베딩 벡터 수가 일치하지 않아 새로 임베딩을 생성합니다.")
        except Exception as e:
            print(f"[경고] 기존 임베딩 파일 로드 중 실패 (새로 생성합니다): {e}")

    # 구식 대용량 파일(movies_embeddings.json)이 존재할 경우 마이그레이션 지원
    elif os.path.exists("movies_embeddings.json"):
        try:
            print("기존 대용량 movies_embeddings.json 파일에서 임베딩 정보를 추출하여 마이그레이션합니다...")
            with open("movies_embeddings.json", "r", encoding="utf-8") as f:
                legacy_data = json.load(f)
            existing_embeddings = {m["title"]: m["embedding"] for m in legacy_data if "embedding" in m}
            print(f"마이그레이션용 기존 임베딩 추출 완료: {len(existing_embeddings)}개")
        except Exception as e:
            print(f"[경고] 레거시 파일 마이그레이션 실패: {e}")

    client = genai.Client()

    output_metadata = []
    output_vectors = []
    new_embeddings_count = 0

    print(f"총 {len(movies)}개의 영화 중 바이너리 포맷 임베딩 작업을 시작합니다...")

    for i, movie in enumerate(movies):
        title = movie["title"]
        category = movie.get("category", "korean")
        
        # 메타데이터 구성 (임베딩 필드 제외)
        meta_item = {
            "title": movie["title"],
            "year": movie["year"],
            "actors": movie["actors"],
            "synopsis": movie["synopsis"],
            "category": category
        }
        output_metadata.append(meta_item)
        
        # 이미 임베딩이 존재하는 경우 재사용
        if title in existing_embeddings:
            output_vectors.append(existing_embeddings[title])
        else:
            # 신규 임베딩 생성
            print(f"[{i+1}/{len(movies)}] 신규 영화 '{title}' 임베딩 생성 중...")
            actors_str = ", ".join(movie["actors"])
            doc = f"제목: {movie['title']}\n개봉년도: {movie['year']}년\n출연배우: {actors_str}\n줄거리: {movie['synopsis']}"
            
            try:
                response = client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=doc
                )
                vector = response.embeddings[0].values
                output_vectors.append(vector)
                new_embeddings_count += 1
            except Exception as e:
                print(f"[오류] '{title}' 임베딩 생성 중 실패: {e}")
                # 실패한 항목은 임시로 0 벡터 지정 (3072차원)
                output_vectors.append([0.0] * 3072)

    # 1. 메타데이터 JSON 저장 (용량 매우 가벼움)
    with open(metadata_output_path, "w", encoding="utf-8") as f:
        json.dump(output_metadata, f, ensure_ascii=False, indent=4)

    # 2. 임베딩 벡터 NumPy 바이너리(npy) 저장
    vectors_array = np.array(output_vectors, dtype=np.float32)
    np.save(embeddings_output_path, vectors_array)

    print(f"\n[마이그레이션 완료!]")
    print(f"- 신규 생성된 임베딩: {new_embeddings_count}개")
    print(f"- 메타데이터 파일 저장 완료: '{metadata_output_path}' (크기: {os.path.getsize(metadata_output_path) / 1024:.2f} KB)")
    print(f"- 임베딩 바이너리 저장 완료: '{embeddings_output_path}' (크기: {os.path.getsize(embeddings_output_path) / 1024 / 1024:.2f} MB)")

if __name__ == "__main__":
    main()
