# /home/ubuntu/facman_AI/headquater_system/Dockerfile

# 1. 베이스 이미지 설정
FROM python:3.11-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 필요한 시스템 패키지 설치 (ffmpeg 등 STT/TTS 모듈에 필요할 수 있음)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    libportaudio2 \
    portaudio19-dev \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 4. 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 애플리케이션 코드 복사
COPY ./modules ./modules
COPY ./routers ./routers
COPY ./config.py .
COPY ./main.py .
# .env 파일은 여기에 포함하지 않습니다.

# 6. 애플리케이션 실행
# 포트는 예시로 8002 사용 (내부 포트)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]