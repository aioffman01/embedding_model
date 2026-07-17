import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Movie(BaseModel):
    title: str = Field(description="영화 제목 (영어 원제 또는 한글 번역 제목)")
    year: int = Field(description="개봉 년도")
    actors: List[str] = Field(description="주요 출연 배우 목록")
    synopsis: str = Field(description="줄거리 (2~3문장 이상으로 상세하게 작성)")

class MovieList(BaseModel):
    movies: List[Movie]

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[오류] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        return

    input_path = "movies.json"
    korean_movies = []

    # 기존 movies.json이 존재하는 경우 로드하여 한국 영화 카테고리 지정
    if os.path.exists(input_path):
        with open(input_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        
        raw_movies = existing_data.get("movies", [])
        for m in raw_movies:
            # 기존 영화에 category 필드가 없으면 korean으로 태깅
            m["category"] = m.get("category", "korean")
            korean_movies.append(m)
        print(f"기존 한국 영화 로드 완료: {len(korean_movies)}개")
    else:
        print("[오류] 기존 한국 영화 데이터가 포함된 movies.json 파일이 존재하지 않습니다.")
        return

    print("Gemini API를 사용하여 2000년 이후 출시된 글로벌 해외 명작 영화 100개 데이터를 수집하는 중...")
    client = genai.Client()

    foreign_movies = []
    
    # 100개가 채워질 때까지 반복하여 해외 영화 수집
    while len(foreign_movies) < 100:
        current_count = len(foreign_movies)
        needed = 100 - current_count
        print(f"현재 수집된 해외 영화: {current_count}개. 100개를 채우기 위해 {needed}개의 영화를 수집을 시도합니다...")

        existing_foreign_titles = [m["title"] for m in foreign_movies]
        
        prompt = (
            f"2000년 이후에 개봉한 글로벌 해외 영화(할리우드, 유럽, 일본, 홍콩 등 한국 제외 국가 영화) 중 "
            f"대중성과 작품성이 검증된 영화 명작 {needed}개를 선정해 주세요.\n"
            f"제외 대상 목록 (중복 금지): {', '.join(existing_foreign_titles)}\n\n"
            f"기존 목록과 중복 없이 정확히 {needed}개의 해외 영화 데이터를 한글로 상세한 줄거리와 함께 JSON 형식에 맞추어 생성해 주세요."
        )

        try:
            response = client.models.generate_content(
                model='gemini-3.1-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=MovieList,
                    temperature=0.3,
                ),
            )

            new_data = json.loads(response.text)
            new_movies = new_data.get("movies", [])
            print(f"이번 시도에서 수집된 신규 해외 영화 수: {len(new_movies)}개")

            for movie in new_movies:
                title = movie["title"]
                if title not in existing_foreign_titles and len(foreign_movies) < 100:
                    movie["category"] = "foreign" # 해외 카테고리 태깅
                    foreign_movies.append(movie)
                    existing_foreign_titles.append(title)
                else:
                    if title in existing_foreign_titles:
                        print(f"[중복 항목 차단] {title}")

        except Exception as e:
            print(f"[API 호출 오류] {e}")
            break

    print(f"최종 해외 영화 수집 완료: {len(foreign_movies)}개")

    # 병합
    all_movies = korean_movies + foreign_movies
    print(f"최종 병합된 영화 수: {len(all_movies)}개 (한국 영화: {len(korean_movies)}개, 해외 영화: {len(foreign_movies)}개)")

    # 저장
    output_data = {"movies": all_movies}
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f"성공적으로 통합 영화 데이터셋이 '{input_path}'에 저장되었습니다.")

if __name__ == "__main__":
    main()
