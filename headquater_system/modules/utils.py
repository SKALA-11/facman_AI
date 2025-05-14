# modules/utils.py

# ISO-639-1 코드 -> 언어명 (한글)
language_map = {
    "ko": "한국어",
    "en": "영어",
    "ja": "일본어",
    "zh": "중국어",
    "es": "스페인어",
    "fr": "프랑스어",
    "de": "독일어",
    "ru": "러시아어",
    "vi": "베트남어",
}

# 풀네임 또는 한글명 -> ISO-639-1 코드 보정을 위한 alias
language_aliases = {
    "english": "en",
    "korean": "ko",
    "japanese": "ja",
    "chinese": "zh",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "russian": "ru",
    "vietnamese": "vi",
    "영어": "en",
    "한국어": "ko",
    "일본어": "ja",
    "중국어": "zh",
    "스페인어": "es",
    "프랑스어": "fr",
    "독일어": "de",
    "러시아어": "ru",
    "베트남어": "vi"
}

def sanitize_language_code(lang):
    """
    감지된 언어 문자열을 ISO-639-1 형식(두 글자)으로 보정합니다.
    예: "english" 또는 "영어" -> "en", "korean" 또는 "한국어" -> "ko".
    """
    if not lang:
        return "ko"
    lang = lang.strip().lower()
    if lang in language_aliases:
        return language_aliases[lang]
    if len(lang) == 2:
        return lang
    return "ko"

def get_log_filenames(detected_language, target_language):
    """
    감지된 소스 언어와 타겟 언어를 기반으로 로그 파일 이름을 반환합니다.
    """
    source_lang = detected_language if detected_language else "auto"
    if source_lang == "auto":
        source_name = "자동감지"
    else:
        source_name = language_map.get(source_lang, "자동감지")
    target_name = language_map.get(target_language, "영어")
    return f"source_log.txt", f"target_log.txt"

def clear_screen():
    # 디버깅 목적으로 화면 클리어를 비활성화할 수 있습니다.
    # os.system('cls' if os.name == 'nt' else 'clear')
    pass

def update_display(detected_language, target_language, recording_status):
    clear_screen()
    source_log, target_log = get_log_filenames(detected_language, target_language)
    print("\n\n")
    print("=" * 60)
    print("🎙️ STT → 번역 → TTS (언어 자동 감지 + VAD)")
    print("=" * 60)
    if not detected_language:
        current_lang = "자동감지"
    else:
        current_lang = language_map.get(detected_language, "자동감지")
    target_name = language_map.get(target_language, "영어")
    print(f"감지된 소스 언어: {current_lang}")
    print(f"타겟 언어: {target_name}")
    print(f"소스 로그: {source_log}")
    print(f"타겟 로그: {target_log}")
    print("=" * 60)
    print(f"상태: {recording_status}")
    print("=" * 60)
