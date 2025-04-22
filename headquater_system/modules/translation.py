# modules/translation.py

import queue, time
import openai
from modules.utils import language_map, get_log_filenames
from config import CLIENT
import sys

def translation_process(user, text):
    """
    메시지를 받아 해당 메시지를 사용자의 target_lang으로 번역한 결과를 반환합니다.
    """
    try:
        # 만약 메시지의 원본 언어와 자신의 대상 언어가 같다면 번역하지 않고 그대로 전달
        if user.source_lang == user.target_lang:
            print(f"[DEBUG] {user.name} 소스 언어와 타겟 언어가 동일하여 번역 없이 전송")
            return text
            
        # 번역 API 호출 (예시: GPT-4o-mini 번역 요청)
        try:
            source_name = language_map.get(user.source_lang, "감지된 언어")
            target_name = language_map.get(user.target_lang)
            response = CLIENT.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"""You are a professional interpreter. When translating from {source_name} to {target_name},
follow these rules:
1. 애매하거나 오해 소지가 있으면 → 명확한 용어로 고쳐 번역한다.
2. 잘못된 근거 정보일 경우 → 부드럽게 재확인하도록 번역한다.
3. 편협·공격적 발언일 경우 → 건설적인 논의 기회로 전환되도록 톤을 조절한다.
4. 반복·딜레이 중인 논의일 경우 → 핵심을 요약해 주제에 이끌어낸다.
5. 감정이 격해진 발언일 경우 → 중립적 완충 역할을 하며 번역한다.
Translate exactly what they say, without any extra commentary."""},
                    {"role": "user", "content": text}
                ]
            )
            translation = response.choices[0].message.content.strip()
            print(f"[DEBUG] {user.name} 번역 결과: {translation}")
        except Exception as e:
            print(f"[DEBUG] {user.name} 번역 오류: {e}", file=sys.stderr)
            translation = text
        return translation
        
    except Exception as e:
        print(f"[DEBUG] {user.name} 번역 처리 중 오류 발생: {e}", file=sys.stderr)
        return text
