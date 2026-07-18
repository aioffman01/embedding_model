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
METADATA_FILE = "movies_metadata.json"
EMBEDDINGS_FILE = "movies_embeddings.npy"

# Gemini 클라이언트 초기화
api_key = os.getenv("GEMINI_API_KEY")
client = None
if api_key:
    client = genai.Client()

# PCA 시각화 데이터 글로벌 캐시
visualization_data_cache = []

def precompute_pca():
    """각 카테고리별로 영화 임베딩을 분리하고, 코사인 유사도(각도 기반)를 보존하기 위해 
    L2 정규화(Normalization)를 수행한 후 PCA(차원 축소)를 적용합니다."""
    global visualization_data_cache
    if not os.path.exists(METADATA_FILE) or not os.path.exists(EMBEDDINGS_FILE):
        print("[경고] PCA 연산을 위한 데이터베이스가 존재하지 않습니다.")
        return

    try:
        from sklearn.decomposition import PCA
        print("코사인 기반 L2 정규화 및 PCA 차원 축소 연산을 시작합니다...")
        
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            movies = json.load(f)
        embeddings = np.load(EMBEDDINGS_FILE)

        visualization_data_cache = []
        categories = ["korean", "foreign", "anime"]

        for cat in categories:
            indices = [i for i, m in enumerate(movies) if m.get("category", "korean") == cat]
            if not indices:
                continue

            cat_embeddings = embeddings[indices]
            
            # [핵심] L2 정규화를 거쳐 벡터의 길이를 1로 고정 (코사인 거리 = 유클리드 거리 공식 성립)
            norms = np.linalg.norm(cat_embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1e-9
            normalized_embeddings = cat_embeddings / norms
            
            # 정규화된 상태에서 PCA 투영 진행
            pca = PCA(n_components=2)
            coords = pca.fit_transform(normalized_embeddings)

            for idx, original_idx in enumerate(indices):
                movie = movies[original_idx]
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
            
            if not os.path.exists(METADATA_FILE):
                self.send_error_response(404, "영화 데이터베이스가 아직 생성되지 않았습니다.")
                return

            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                movies = json.load(f)

            filtered_movies = [m for m in movies if m.get("category", "korean") == category]
            self.send_json_response(filtered_movies)
            return

        # 2. 카테고리별 고속 시맨틱 검색 API
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

            if not os.path.exists(METADATA_FILE) or not os.path.exists(EMBEDDINGS_FILE):
                self.send_error_response(404, "영화 데이터베이스가 아직 생성되지 않았습니다.")
                return

            try:
                response = client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=query
                )
                query_vector = np.array(response.embeddings[0].values, dtype=np.float32)

                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    movies = json.load(f)
                embeddings = np.load(EMBEDDINGS_FILE)

                filtered_indices = [i for i, m in enumerate(movies) if m.get("category", "korean") == category]
                
                if not filtered_indices:
                    self.send_json_response([])
                    return

                category_metadata = [movies[i] for i in filtered_indices]
                category_embeddings = embeddings[filtered_indices]

                # 고속 코사인 유사도 벡터화 연산
                dot_products = np.dot(category_embeddings, query_vector)
                query_norm = np.linalg.norm(query_vector)
                movie_norms = np.linalg.norm(category_embeddings, axis=1)

                norms_product = movie_norms * query_norm
                norms_product[norms_product == 0] = 1e-9

                similarities = dot_products / norms_product

                results = []
                for idx, sim in enumerate(similarities):
                    movie = category_metadata[idx]
                    results.append({
                        "title": movie["title"],
                        "year": movie["year"],
                        "actors": movie["actors"],
                        "synopsis": movie["synopsis"],
                        "category": movie.get("category", "korean"),
                        "similarity": float(sim)
                    })

                results.sort(key=lambda x: x["similarity"], reverse=True)
                top_3 = results[:3]
                self.send_json_response(top_3)

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
        print("[경고] GEMINI_API_KEY가 설정되지 않았습니다.")

    try:
        precompute_pca()
    except Exception as e:
        print(f"[알림] 시작 중 PCA 사전 연산 보류: {e}")

    Handler = MovieSearchAPIHandler
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"==================================================")
        print(f" [코사인 기반 시각화 연동] 웹 서버가 가동되었습니다.")
        print(f" 접속 주소: http://localhost:{PORT}")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n웹 서버를 종료합니다.")

if __name__ == "__main__":
    main()
