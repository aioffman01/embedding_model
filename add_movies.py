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
    title: str = Field(description="영화 제목")
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
    if not os.path.exists(input_path):
        print(f"[오류] 기존 '{input_path}' 파일이 존재하지 않습니다.")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        existing_data = json.load(f)
    
    unique_movies = existing_data.get("movies", [])
    
    client = genai.Client()
    
    # 100개가 채워질 때까지 반복해서 수집
    while len(unique_movies) < 100:
        current_count = len(unique_movies)
        needed = 100 - current_count
        print(f"현재 영화 개수: {current_count}개. 100개를 채우기 위해 {needed}개의 새로운 한국 영화 데이터 수집을 시도합니다...")
        
        existing_titles = [m["title"] for m in unique_movies]
        
        prompt = (
            f"2000년 이후에 개봉한 한국 영화 중 다음 기존 영화 목록에 절대 포함되지 않는 새로운 영화 {needed}개를 선정해 주세요.\n"
            f"제외 대상 목록: {', '.join(existing_titles)}\n\n"
            f"기존 목록과 중복 없이 정확히 {needed}개의 영화 데이터를 JSON 포맷에 맞추어 생성해 주세요."
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
            print(f"이번 시도에서 수집된 신규 영화 수: {len(new_movies)}개")
            
            # 중복 체크하며 병합
            for movie in new_movies:
                title = movie["title"]
                if title not in existing_titles and len(unique_movies) < 100:
                    unique_movies.append(movie)
                    existing_titles.append(title)
                else:
                    if title in existing_titles:
                        print(f"[중복 항목 차단] {title}")
                        
        except Exception as e:
            print(f"[API 호출 오류] {e}")
            break

    print(f"최종 수집 완료된 영화 수: {len(unique_movies)}개")
    
    # 업데이트된 파일 저장
    output_data = {"movies": unique_movies}
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
        
    print(f"데이터가 성공적으로 '{input_path}'에 100개 목록으로 갱신되었습니다.")

if __name__ == "__main__":
    main()
