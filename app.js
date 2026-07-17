document.addEventListener("DOMContentLoaded", () => {
    // DOM 요소
    const searchForm = document.getElementById("search-form");
    const searchQueryInput = document.getElementById("search-query");
    const resetBtn = document.getElementById("reset-btn");
    const resultsSummary = document.getElementById("results-summary");
    const movieGrid = document.getElementById("movie-grid");
    const categoryTabButtons = document.querySelectorAll(".tab-btn");
    
    // 내비게이션 탭 스위처 요소
    const navSearch = document.getElementById("nav-search");
    const navViz = document.getElementById("nav-viz");
    const searchView = document.getElementById("search-view");
    const vizView = document.getElementById("viz-view");

    let currentCategory = "korean"; // 기본값: 한국 영화
    let chartInstance = null;

    const categoryLabels = {
        "korean": "한국 영화",
        "foreign": "해외 영화",
        "anime": "일본 애니메이션"
    };

    // ==========================================
    // 1. 뷰 패널 전환 제어
    // ==========================================
    navSearch.addEventListener("click", () => {
        navSearch.classList.add("active");
        navViz.classList.remove("active");
        searchView.classList.remove("hidden");
        vizView.classList.add("hidden");
    });

    navViz.addEventListener("click", () => {
        navViz.classList.add("active");
        navSearch.classList.remove("active");
        vizView.classList.remove("hidden");
        searchView.classList.add("hidden");
        
        // 시각화 차트 초기 구동
        initVisualization();
    });

    // ==========================================
    // 2. 영화 목록/검색 비동기 처리
    // ==========================================
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
                    <p class="movie-actors"><strong>출연/감독:</strong> ${actorsList}</p>
                    <p class="movie-synopsis">${movie.synopsis}</p>
                </div>
            `;
            movieGrid.appendChild(card);
        });
    }

    function showLoading(message) {
        movieGrid.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner"></div>
                <p>${message}</p>
            </div>
        `;
    }

    function showError(message) {
        movieGrid.innerHTML = `<div class="error-message">오류 발생: ${message}</div>`;
        resultsSummary.textContent = "데이터 처리에 실패했습니다";
    }

    // ==========================================
    // 3. Chart.js 시각화 2D 렌더링
    // ==========================================
    function loadChartJS() {
        return new Promise((resolve, reject) => {
            if (window.Chart) {
                resolve();
                return;
            }
            const script = document.createElement("script");
            script.src = "https://cdn.jsdelivr.net/npm/chart.js";
            script.onload = () => resolve();
            script.onerror = () => reject(new Error("Chart.js CDN 로딩 중 오류 발생"));
            document.head.appendChild(script);
        });
    }

    async function initVisualization() {
        const ctx = document.getElementById("similarity-chart").getContext("2d");
        
        try {
            await loadChartJS();
            
            // 데이터 로드
            const response = await fetch("/api/visualization");
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || "시각화 데이터를 로드하지 못했습니다.");
            }
            const rawData = await response.json();

            // 카테고리별 데이터셋으로 분류
            const datasets = {
                korean: { label: "한국 영화", data: [], color: "#ec4899" }, // 네온 핑크
                foreign: { label: "해외 영화", data: [], color: "#6366f1" }, // 네온 블루
                anime: { label: "일본 애니메이션", data: [], color: "#10b981" } // 네온 그린
            };

            rawData.forEach(item => {
                const cat = item.category || "korean";
                if (datasets[cat]) {
                    datasets[cat].data.push({
                        x: item.x,
                        y: item.y,
                        // 마우스 호버용 영화 메타데이터
                        title: item.title,
                        year: item.year,
                        actors: item.actors,
                        synopsis: item.synopsis
                    });
                }
            });

            // 차트 인스턴스 초기화 (기존 차트 해제)
            if (chartInstance) {
                chartInstance.destroy();
            }

            // Chart.js 2D 산점도 그리기
            chartInstance = new Chart(ctx, {
                type: 'scatter',
                data: {
                    datasets: Object.keys(datasets).map(key => {
                        return {
                            label: datasets[key].label,
                            data: datasets[key].data,
                            backgroundColor: datasets[key].color,
                            borderColor: "transparent",
                            pointRadius: 6,
                            pointHoverRadius: 9,
                            pointHoverBackgroundColor: "#ffffff",
                            pointHoverBorderColor: datasets[key].color,
                            pointHoverBorderWidth: 3
                        };
                    })
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: {
                                color: "#f3f4f6", // 다크 모드용 흰색 범례 글씨
                                font: {
                                    family: "'Outfit', sans-serif",
                                    size: 14,
                                    weight: 600
                                },
                                padding: 20
                            }
                        },
                        tooltip: {
                            backgroundColor: "rgba(15, 17, 26, 0.95)",
                            titleColor: "#ffffff",
                            titleFont: {
                                family: "'Outfit', sans-serif",
                                size: 15,
                                weight: 700
                            },
                            bodyColor: "#d1d5db",
                            bodyFont: {
                                family: "'Inter', sans-serif",
                                size: 12
                            },
                            borderColor: "rgba(255,255,255,0.1)",
                            borderWidth: 1,
                            padding: 15,
                            cornerRadius: 12,
                            displayColors: false,
                            callbacks: {
                                title: function(context) {
                                    const point = context[0].raw;
                                    return `${point.title} (${point.year}년)`;
                                },
                                label: function(context) {
                                    const point = context.raw;
                                    const actors = point.actors.slice(0, 3).join(", ");
                                    const truncatedSynopsis = point.synopsis.length > 80 
                                        ? point.synopsis.substring(0, 80) + "..." 
                                        : point.synopsis;

                                    return [
                                        `출연/감독: ${actors}`,
                                        "",
                                        "줄거리 요약:",
                                        truncatedSynopsis
                                    ];
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                color: "rgba(255,255,255,0.03)"
                            },
                            ticks: {
                                color: "rgba(255,255,255,0.2)"
                            }
                        },
                        y: {
                            grid: {
                                color: "rgba(255,255,255,0.03)"
                            },
                            ticks: {
                                color: "rgba(255,255,255,0.2)"
                            }
                        }
                    }
                }
            });

        } catch (error) {
            console.error("차트 생성 중 오류:", error);
            document.getElementById("similarity-chart").parentElement.innerHTML = 
                `<div class="error-message" style="margin-top: 5rem;">시각화 분석 차트를 불러오지 못했습니다: ${error.message}</div>`;
        }
    }

    // ==========================================
    // 4. 일반 이벤트 처리
    // ==========================================
    categoryTabButtons.forEach(button => {
        button.addEventListener("click", () => {
            if (button.classList.contains("active")) return;

            categoryTabButtons.forEach(btn => btn.classList.remove("active"));
            button.classList.add("active");

            currentCategory = button.getAttribute("data-category");
            searchQueryInput.value = "";
            fetchMovies();
        });
    });

    searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const query = searchQueryInput.value.trim();
        if (query) {
            searchMovies(query);
        }
    });

    resetBtn.addEventListener("click", () => {
        searchQueryInput.value = "";
        fetchMovies();
    });

    // 시작
    fetchMovies();
});

// CSS 페이드인 및 키프레임 추가
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
