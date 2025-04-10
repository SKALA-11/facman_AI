'''
project_root/
├── config.py           # 전역 설정 (API 키, 오디오 설정, 전역 클라이언트 등)
├── main.py             # 프로그램의 진입점: 각 모듈을 불러와 스레드 실행
└── modules/
    ├── __init__.py
    ├── audio.py        # 오디오 캡처 관련 함수 및 전역 audio_queue, 녹음 제어 Event 등
    ├── stt.py          # STT 처리 (Whisper API, VAD, 언어 감지)
    ├── translation.py  # 번역 처리 (GPT-4o-mini를 사용)
    ├── tts.py          # TTS 처리 (GPT-4o-mini-tts를 사용)
    └── utils.py        # 공통 유틸리티 함수 (언어 보정, 로그 파일명 생성, 디스플레이 업데이트 등)
'''