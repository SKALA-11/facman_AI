# /home/ubuntu/facman_AI/local_system/Dockerfile

# 1. 베이스 이미지 설정
FROM python:3.11-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 필요한 시스템 패키지 설치 (필요한 경우)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc

# 4. 의존성 파일 복사 및 설치
COPY requirements.txt .
# --no-cache-dir: 캐시 사용 안함 (이미지 크기 줄이기)
# -r: requirements.txt 파일 사용
RUN pip install --no-cache-dir -r requirements.txt

# 5. 애플리케이션 코드 복사
# src 디렉토리와 필요한 다른 파일들을 /app/으로 복사
COPY ./src ./src
COPY ./vector_db ./vector_db
# .env 파일은 여기에 포함하지 않습니다. (docker-compose에서 처리)

RUN python ./src/db_migration.py

# 6. 애플리케이션 실행
# main.py가 src 폴더 안에 있다고 가정
# 포트는 예시로 8001 사용 (내부 포트)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]