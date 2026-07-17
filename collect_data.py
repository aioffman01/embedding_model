import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Pydantic 모델 정의 (구조화된 출력용)
class Movie(BaseModel):
    title: str = Field(description="영화 제목 (예: 기생충)")
    year: int = Field(description="개봉 년도 (예: 2019)")
    actors: List[str] = Field(description="주요 출연 배우 목록")
    synopsis: str = Field(description="줄거리 (2~3문장 이상으로 상세하게 작성)")

class MovieList(BaseModel):
    movies: List[Movie]

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[오류] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        print(".env 파일을 생성하여 GEMINI_API_KEY=your_api_key_here 형식으로 작성해 주세요.")
        return

    print("Gemini API를 사용하여 2000년 이후 출시된 한국 영화 50개 데이터를 수집하는 중...")
    client = genai.Client()

    prompt = (
        "2000년 이후에 개봉한 한국 영화 중 흥행했거나 평론가들에게 극찬을 받은 영화 50개를 선정해주세요. "
        "장르가 다양하게 섞이도록 해주세요(스릴러, 로맨스, 코미디, SF, 액션, 드라마 등). "
        "반드시 한국 영화로만 구성해야 하며, 제작/개봉 연도는 2000년부터 2026년 사이여야 합니다. "
        "중복 없이 정확히 50개의 영화 목록을 JSON 형식에 맞추어 출력해주세요."
    )

    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=MovieList,
                temperature=0.2, # 일관성 있는 결과를 위해 낮은 온도로 설정
            ),
        )

        # JSON 파싱 및 저장
        data = json.loads(response.text)
        
        # 영화 수 확인
        movie_count = len(data.get("movies", []))
        print(f"성공적으로 {movie_count}개의 영화 데이터를 생성하였습니다.")

        output_path = "movies.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        print(f"데이터가 '{output_path}' 파일에 저장되었습니다.")

    except Exception as e:
        print(f"[오류 발생] 데이터 수집 중 문제가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
