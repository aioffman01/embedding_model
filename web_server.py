import http.server
import socketserver
import urllib.parse
import json
import os
import numpy as np
from google import genai
from dotenv import load_dotenv

# .env 로드
load_dotenv()

PORT = 8000
EMBEDDINGS_FILE = "movies_embeddings.json"

# Gemini 클라이언트 초기화
api_key = os.getenv("GEMINI_API_KEY")
client = None
if api_key:
    client = genai.Client()

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

class MovieSearchAPIHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # 1. 카테고리별 영화 목록 API
        if path == "/api/movies":
            category = query_params.get("category", ["korean"])[0]
            
            if not os.path.exists(EMBEDDINGS_FILE):
                self.send_error_response(404, "영화 데이터베이스가 아직 생성되지 않았습니다.")
                return

            with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
                movies = json.load(f)

            # 카테고리 필터링 적용 (기본값 korean)
            filtered_movies = [m for m in movies if m.get("category", "korean") == category]

            movies_summary = []
            for movie in filtered_movies:
                movies_summary.append({
                    "title": movie["title"],
                    "year": movie["year"],
                    "actors": movie["actors"],
                    "synopsis": movie["synopsis"],
                    "category": movie.get("category", "korean")
                })

            self.send_json_response(movies_summary)
            return

        # 2. 카테고리별 시맨틱 검색 API
        elif path == "/api/search":
            q_list = query_params.get("q", [])
            category = query_params.get("category", ["korean"])[0]
            
            if not q_list or not q_list[0].strip():
                self.send_error_response(400, "검색어(q) 파라미터가 유효하지 않습니다.")
                return

            query = q_list[0].strip()

            if not client:
                self.send_error_response(500, "Gemini API 키가 백엔드에 설정되지 않았습니다.")
                return

            if not os.path.exists(EMBEDDINGS_FILE):
                self.send_error_response(404, "영화 데이터베이스가 아직 생성되지 않았습니다.")
                return

            try:
                # 검색어 임베딩 생성 (Gemini API 호출)
                response = client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=query
                )
                query_vector = response.embeddings[0].values

                # 로컬 코사인 유사도 계산
                with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
                    movies = json.load(f)

                # 선택된 카테고리에 속하는 영화들만 필터링하여 유사도 계산
                filtered_movies = [m for m in movies if m.get("category", "korean") == category]

                results = []
                for movie in filtered_movies:
                    similarity = cosine_similarity(query_vector, movie["embedding"])
                    results.append({
                        "title": movie["title"],
                        "year": movie["year"],
                        "actors": movie["actors"],
                        "synopsis": movie["synopsis"],
                        "category": movie.get("category", "korean"),
                        "similarity": similarity
                    })

                # 유사도 기준 내림차순 정렬 및 상위 3개 추출
                results.sort(key=lambda x: x["similarity"], reverse=True)
                top_3 = results[:3]

                self.send_json_response(top_3)

            except Exception as e:
                self.send_error_response(500, f"검색 중 서버 오류 발생: {str(e)}")
            return

        # 3. 그 외 경로는 기본 정적 파일 서빙
        else:
            super().do_GET()

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        response_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def send_error_response(self, status_code, message):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        response_bytes = json.dumps({"error": message}, ensure_ascii=False).encode('utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

def main():
    if not api_key:
        print("[경고] GEMINI_API_KEY가 로드되지 않았습니다. 시맨틱 검색 API가 오동작할 수 있습니다.")

    Handler = MovieSearchAPIHandler
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"==================================================")
        print(f" 카테고리 지원 영화 검색 웹 서버가 가동되었습니다.")
        print(f" 접속 주소: http://localhost:{PORT}")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n웹 서버를 종료합니다.")

if __name__ == "__main__":
    main()
