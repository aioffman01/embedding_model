import http.server
import socketserver
import urllib.parse
import json
import os
import numpy as np
from google import genai
from dotenv import load_dotenv
from supabase import create_client, Client

# 스크립트 디렉토리 획득
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# .env 로드 (절대 경로)
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

PORT = 8000

# Gemini 클라이언트 초기화
api_key = os.getenv("GEMINI_API_KEY")
client = None
if api_key:
    client = genai.Client()

# Supabase 클라이언트 초기화
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)

# PCA 시각화 데이터 글로벌 캐시
visualization_data_cache = []

def precompute_pca():
    """Supabase DB에서 영화 임베딩 데이터를 불러온 뒤,
    각 카테고리별로 L2 정규화 및 PCA 차원 축소 연산을 수행하여 캐시합니다."""
    global visualization_data_cache
    if not supabase:
        print("[경고] Supabase 클라이언트가 초기화되지 않아 PCA를 수행할 수 없습니다.")
        return

    try:
        from sklearn.decomposition import PCA
        print("Supabase로부터 영화 임베딩을 불러와 PCA 차원 축소 연산을 수행합니다...")
        
        # DB에서 전체 영화 데이터 (임베딩 포함) 일괄 조회
        res = supabase.table("movies").select("title, year, actors, synopsis, category, embedding").execute()
        movies = res.data
        
        if not movies:
            print("[경고] DB에 영화 데이터가 존재하지 않습니다.")
            return

        visualization_data_cache = []
        categories = ["korean", "foreign", "anime"]

        for cat in categories:
            # 해당 카테고리의 영화 필터링
            cat_movies = [m for m in movies if m.get("category", "korean") == cat]
            if not cat_movies:
                continue

            # 임베딩 데이터 수치화
            cat_embeddings = np.array([m["embedding"] for m in cat_movies], dtype=np.float32)
            
            # L2 정규화 (코사인 거리 보존)
            norms = np.linalg.norm(cat_embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1e-9
            normalized_embeddings = cat_embeddings / norms
            
            # 2차원 투영
            pca = PCA(n_components=2)
            coords = pca.fit_transform(normalized_embeddings)

            for idx, movie in enumerate(cat_movies):
                visualization_data_cache.append({
                    "title": movie["title"],
                    "year": movie["year"],
                    "actors": movie["actors"],
                    "synopsis": movie["synopsis"],
                    "category": cat,
                    "x": float(coords[idx, 0]),
                    "y": float(coords[idx, 1])
                })
        
        print(f"코사인 기반 PCA 연산 완료 (총 {len(visualization_data_cache)}개 영화 캐싱됨)")
    except Exception as e:
        print(f"[오류] 코사인 기반 PCA 계산 중 에러 발생: {e}")

class MovieSearchAPIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # backend 폴더의 상위 폴더(..) 하위의 frontend 폴더를 정적 파일 루트로 지정
        script_dir = os.path.dirname(os.path.abspath(__file__))
        frontend_dir = os.path.abspath(os.path.join(script_dir, "..", "frontend"))
        super().__init__(*args, directory=frontend_dir, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # 1. 카테고리별 영화 목록 API (Supabase 조회)
        if path == "/api/movies":
            category = query_params.get("category", ["korean"])[0]
            
            if not supabase:
                self.send_error_response(500, "Supabase 클라이언트가 설정되지 않았습니다.")
                return

            try:
                # 임베딩 컬럼은 네트워크 트래픽 절감을 위해 select에서 제외
                res = supabase.table("movies") \
                    .select("title, year, actors, synopsis, category") \
                    .eq("category", category) \
                    .execute()
                self.send_json_response(res.data)
            except Exception as e:
                self.send_error_response(500, f"데이터베이스 조회 실패: {str(e)}")
            return

        # 2. 카테고리별 pgvector RPC 시맨틱 검색 API (Supabase 계산)
        elif path == "/api/search":
            q_list = query_params.get("q", [])
            category = query_params.get("category", ["korean"])[0]
            
            if not q_list or not q_list[0].strip():
                self.send_error_response(400, "검색어(q) 파라미터가 유효하지 않습니다.")
                return

            query = q_list[0].strip()

            if not client:
                self.send_error_response(500, "Gemini API 키가 설정되지 않았습니다.")
                return

            if not supabase:
                self.send_error_response(500, "Supabase 데이터베이스가 연결되어 있지 않습니다.")
                return

            try:
                # 2-1. 검색어 실시간 임베딩 생성 (Gemini)
                response = client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=query
                )
                query_vector = response.embeddings[0].values

                # 2-2. 데이터베이스 pgvector RPC 함수 호출 (로컬 메모리 연산 제거)
                res = supabase.rpc("match_movies", {
                    "query_embedding": query_vector,
                    "match_threshold": 0.0,
                    "match_count": 3,
                    "filter_category": category
                }).execute()

                self.send_json_response(res.data)

            except Exception as e:
                self.send_error_response(500, f"검색 중 서버 오류 발생: {str(e)}")
            return

        # 3. 2D 시각화 데이터 API (PCA 결과 반환)
        elif path == "/api/visualization":
            global visualization_data_cache
            if not visualization_data_cache:
                precompute_pca()
            
            if not visualization_data_cache:
                self.send_error_response(500, "시각화 데이터를 연산하지 못했습니다.")
                return

            self.send_json_response(visualization_data_cache)
            return

        # 4. 그 외 정적 파일 서빙
        else:
            super().do_GET()

    def send_json_response(self, data):
        self.send_value_response(200, data)

    def send_error_response(self, status_code, message):
        self.send_value_response(status_code, {"error": message})

    def send_value_response(self, status_code, value):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        response_bytes = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

def main():
    if not api_key:
        print("[경고] GEMINI_API_KEY가 설정되지 않았습니다.")
    if not supabase:
        print("[경고] Supabase 환경 변수가 올바르게 설정되지 않았습니다.")

    try:
        precompute_pca()
    except Exception as e:
        print(f"[알림] 시작 중 PCA 사전 연산 보류: {e}")

    Handler = MovieSearchAPIHandler
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"==================================================")
        print(f" [로컬 Supabase & pgvector 연동] 웹 서버가 가동되었습니다.")
        print(f" 접속 주소: http://localhost:{PORT}")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n웹 서버를 종료합니다.")

if __name__ == "__main__":
    main()
