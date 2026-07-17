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
    title: str = Field(description="애니메이션 제목 (한국어 공식 개봉명 또는 널리 알려진 제목)")
    year: int = Field(description="제작/개봉 연도 (연도 제한 없음)")
    actors: List[str] = Field(description="주요 성우 목록 또는 감독 이름")
    synopsis: str = Field(description="줄거리 (2~3문장 이상으로 상세하게 작성)")

class MovieList(BaseModel):
    movies: List[Movie]

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[오류] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        return

    input_path = "movies.json"
    existing_movies = []

    if os.path.exists(input_path):
        with open(input_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        existing_movies = existing_data.get("movies", [])
        print(f"기존 영화 로드 완료: {len(existing_movies)}개")
    else:
        print("[오류] movies.json 파일이 존재하지 않습니다.")
        return

    print("Gemini API를 사용하여 일본 인기 애니메이션 100개 데이터를 수집하는 중...")
    client = genai.Client()

    anime_movies = []
    
    # 100개가 채워질 때까지 반복하여 일본 애니메이션 수집
    while len(anime_movies) < 100:
        current_count = len(anime_movies)
        needed = 100 - current_count
        print(f"현재 수집된 애니메이션: {current_count}개. 100개를 채우기 위해 {needed}개의 데이터를 추가 수집합니다...")

        existing_anime_titles = [m["title"] for m in anime_movies]
        
        prompt = (
            f"일본의 역대 인기 애니메이션(극장판 및 극장판급 명작 시리즈) 중 "
            f"대중성과 작품성이 널리 검증된 명작 {needed}개를 선정해 주세요. 제작 연도에 제한은 전혀 없습니다 (고전 명작 포함 가능).\n"
            f"제외 대상 목록 (중복 금지): {', '.join(existing_anime_titles)}\n\n"
            f"기존 목록과 중복 없이 정확히 {needed}개의 일본 애니메이션 데이터를 한글로 상세한 줄거리 및 감독/성우 정보와 함께 JSON 형식에 맞추어 생성해 주세요."
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
            print(f"이번 시도에서 수집된 신규 애니메이션 수: {len(new_movies)}개")

            for movie in new_movies:
                title = movie["title"]
                if title not in existing_anime_titles and len(anime_movies) < 100:
                    movie["category"] = "anime" # 애니메이션 카테고리 태깅
                    anime_movies.append(movie)
                    existing_anime_titles.append(title)
                else:
                    if title in existing_anime_titles:
                        print(f"[중복 항목 차단] {title}")

        except Exception as e:
            print(f"[API 호출 오류] {e}")
            break

    print(f"최종 일본 애니메이션 수집 완료: {len(anime_movies)}개")

    # 기존 데이터와 병합
    all_movies = existing_movies + anime_movies
    print(f"최종 병합된 영화 수: {len(all_movies)}개")

    # 저장
    output_data = {"movies": all_movies}
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f"성공적으로 일본 애니메이션 카테고리가 추가된 영화 데이터셋이 '{input_path}'에 저장되었습니다.")

if __name__ == "__main__":
    main()
