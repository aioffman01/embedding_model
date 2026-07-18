#!/bin/bash

# Rocky Linux 9+ 영화 시맨틱 검색 서버 설정 스크립트
# 실행 방법: sudo bash setup.sh

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================================================${NC}"
echo -e "${GREEN}         Rocky Linux용 영화 시맨틱 검색 엔진 설정 시작                 ${NC}"
echo -e "${GREEN}========================================================================${NC}"

# 1. 루트 권한 확인
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[오류] 이 스크립트는 root 권한(sudo)으로 실행해야 합니다.${NC}"
  exit 1
fi

# 현재 프로젝트 경로 추출
PROJECT_DIR=$(dirname "$(readlink -f "$0")")/..
cd "$PROJECT_DIR" || exit 1
echo -e "${YELLOW}[정보] 프로젝트 경로: $PROJECT_DIR${NC}"

# 2. 필수 시스템 패키지 설치
echo -e "\n${YELLOW}[1단계] dnf 패키지 업데이트 및 Python3, Git, Firewall 설치...${NC}"
dnf update -y --exclude=kernel*
dnf install -y python3 python3-pip git firewalld

# 방화벽 활성화 및 실행 확인
systemctl enable --now firewalld

# 3. 파이썬 가상환경(Virtual Environment) 구축
echo -e "\n${YELLOW}[2단계] 파이썬 가상환경 생성 및 종속성 설치...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}가상환경(venv) 생성 완료.${NC}"
fi

# 가상환경 업그레이드 및 라이브러리 설치
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
echo -e "${GREEN}의존성 패키지 설치 완료.${NC}"

# 4. 방화벽 설정 (Port 8000 허용)
echo -e "\n${YELLOW}[3단계] 방화벽 설정 (TCP 8000 포트 오픈)...${NC}"
firewall-cmd --zone=public --add-port=8000/tcp --permanent
firewall-cmd --reload
echo -e "${GREEN}방화벽 설정 완료. (포트 8000 개방)${NC}"

# 5. Systemd 서비스 등록 안내 및 템플릿 생성
echo -e "\n${YELLOW}[4단계] Systemd 서비스 등록 파일 생성...${NC}"
SERVICE_FILE="/etc/systemd/system/movie-search.service"

# .env 파일에서 API 키 추출 시도
API_KEY=""
if [ -f "backend/.env" ]; then
    API_KEY=$(grep GEMINI_API_KEY backend/.env | cut -d '=' -f2)
fi

# 서비스 파일 덮어쓰기
cat <<EOF > $SERVICE_FILE
[Unit]
Description=Cinema Semantic Search Engine Web Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR/backend
ExecStart=$PROJECT_DIR/venv/bin/python web_server.py
Restart=always
Environment="GEMINI_API_KEY=${API_KEY}"

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo -e "${GREEN}Systemd 서비스 파일 생성 완료: $SERVICE_FILE${NC}"
if [ -z "$API_KEY" ]; then
    echo -e "${RED}[주의] backend/.env 파일에서 GEMINI_API_KEY를 찾지 못했습니다.${NC}"
    echo -e "${RED}생성된 서비스 파일($SERVICE_FILE) 내에 API 키를 수동으로 지정한 뒤 구동해주세요.${NC}"
fi

echo -e "\n${GREEN}========================================================================${NC}"
echo -e "${GREEN}                         설정 완료!                                     ${NC}"
echo -e "${GREEN}========================================================================${NC}"
echo -e "서비스를 시작하려면 다음 명령어를 실행하십시오:"
echo -e "  sudo systemctl enable --now movie-search"
echo -e ""
echo -e "서비스 상태 확인:"
echo -e "  sudo systemctl status movie-search"
echo -e ""
echo -e "접속 주소: http://[서버_IP_주소]:8000"
echo -e "${GREEN}========================================================================${NC}"
