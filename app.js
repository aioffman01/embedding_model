document.addEventListener("DOMContentLoaded", () => {
    const searchForm = document.getElementById("search-form");
    const searchQueryInput = document.getElementById("search-query");
    const resetBtn = document.getElementById("reset-btn");
    const resultsSummary = document.getElementById("results-summary");
    const movieGrid = document.getElementById("movie-grid");
    const tabButtons = document.querySelectorAll(".tab-btn");

    let currentCategory = "korean"; // 기본값: 한국 영화

    const categoryLabels = {
        "korean": "한국 영화",
        "foreign": "해외 영화",
        "anime": "일본 애니메이션"
    };

    // 1. 카테고리별 영화 데이터 가져오기
    async function fetchMovies() {
        const categoryLabel = categoryLabels[currentCategory] || "영화";
        showLoading(`${categoryLabel} 목록을 불러오는 중입니다...`);
        try {
            const response = await fetch(`/api/movies?category=${currentCategory}`);
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || "영화 목록을 가져오지 못했습니다.");
            }
            const movies = await response.json();
            renderMovies(movies);
            resultsSummary.innerHTML = `${categoryLabel} 목록 (<span id="movie-count">${movies.length}</span>개)`;
            resetBtn.classList.add("hidden");
        } catch (error) {
            showError(error.message);
        }
    }

    // 2. 영화 검색 기능
    async function searchMovies(query) {
        const categoryLabel = categoryLabels[currentCategory] || "영화";
        showLoading(`'${query}' 검색 결과를 분석 중입니다...`);
        try {
            const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&category=${currentCategory}`);
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || "검색을 완료하지 못했습니다.");
            }
            const results = await response.json();
            
            if (results.length === 0) {
                movieGrid.innerHTML = `<div class="no-results">검색 결과가 없습니다. 다른 검색어를 입력해보세요!</div>`;
                resultsSummary.textContent = "검색 결과가 없습니다";
            } else {
                renderMovies(results, true);
                resultsSummary.innerHTML = `${categoryLabel} 내 검색 결과 - 가장 유사한 영화 <span class="gradient-text">Top ${results.length}</span>`;
            }
            
            resetBtn.classList.remove("hidden");
        } catch (error) {
            showError(error.message);
        }
    }

    // 3. 영화 카드 렌더링
    function renderMovies(movies, isSearch = false) {
        movieGrid.innerHTML = "";
        
        movies.forEach((movie, index) => {
            const card = document.createElement("div");
            card.className = "movie-card";
            card.style.animation = `fadeIn 0.5s ease forwards ${index * 0.05}s`;
            card.style.opacity = 0;

            const actorsList = movie.actors.join(", ");
            
            let similarityBadgeHtml = "";
            if (isSearch && movie.similarity !== undefined) {
                const simPercentage = (movie.similarity * 100).toFixed(1);
                similarityBadgeHtml = `<span class="similarity-badge">유사도: ${simPercentage}%</span>`;
            }

            card.innerHTML = `
                <div class="movie-card-header">
                    <h3 class="movie-title">${movie.title}</h3>
                    <div class="movie-meta">
                        <span class="movie-year">${movie.year}년</span>
                        ${similarityBadgeHtml}
                    </div>
                </div>
                <div class="movie-card-body">
                    <p class="movie-actors"><strong>출연:</strong> ${actorsList}</p>
                    <p class="movie-synopsis">${movie.synopsis}</p>
                </div>
            `;
            movieGrid.appendChild(card);
        });
    }

    // 헬퍼: 로딩 표시
    function showLoading(message) {
        movieGrid.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner"></div>
                <p>${message}</p>
            </div>
        `;
    }

    // 헬퍼: 에러 표시
    function showError(message) {
        movieGrid.innerHTML = `<div class="error-message">오류 발생: ${message}</div>`;
        resultsSummary.textContent = "검색에 실패했습니다";
    }

    // 탭 버튼 클릭 이벤트 처리
    tabButtons.forEach(button => {
        button.addEventListener("click", () => {
            if (button.classList.contains("active")) return;

            // 탭 스타일 전환
            tabButtons.forEach(btn => btn.classList.remove("active"));
            button.classList.add("active");

            // 상태 변경 및 리프레시
            currentCategory = button.getAttribute("data-category");
            searchQueryInput.value = ""; // 검색어 초기화
            fetchMovies();
        });
    });

    // 이벤트 리스너: 검색 폼 제출
    searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const query = searchQueryInput.value.trim();
        if (query) {
            searchMovies(query);
        }
    });

    // 이벤트 리스너: 초기화(전체 보기) 버튼
    resetBtn.addEventListener("click", () => {
        searchQueryInput.value = "";
        fetchMovies();
    });

    // 초기 로딩
    fetchMovies();
});

// CSS 페이드인 키프레임 동적 추가
const styleSheet = document.createElement("style");
styleSheet.textContent = `
    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    .spinner {
        width: 40px;
        height: 40px;
        border: 4px solid rgba(255, 255, 255, 0.1);
        border-top-color: var(--accent-blue);
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 1rem auto;
    }
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(styleSheet);
