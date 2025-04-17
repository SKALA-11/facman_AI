# modules/translation.py

import queue, time
import openai
from modules.utils import language_map, get_log_filenames
from config import CLIENT
import sys

def translation_thread(user):
    """
    사용자 객체의 sentence_queue에서 메시지를 받아, 
    해당 메시지를 사용자의 target_lang으로 번역한 결과를
    user.translation_queue 및 user.translated_queue에 넣습니다.
    """
    while True:
        try:
            # 메시지: {"speaker": speaker_name, "text": text, "source_lang": source_lang}
            # message = user.sentence_queue.get(timeout=1)
            # text = message.get("text")
            # source_lang = message.get("source_lang", user.source_lang)
            # speaker_name = message.get("speaker")
            text, source_lang = user.sentence_queue.get(timeout=1)
            
            print(f"[DEBUG] {user.name}이 번역할 메시지: '{text}' (소스 언어: {source_lang})")

            # 만약 메시지의 원본 언어와 자신의 대상 언어가 같다면 번역하지 않고 그대로 전달
            if source_lang == user.target_lang:
                print(f"[DEBUG] {user.name}: 소스 언어와 타겟 언어가 동일하여 번역 없이 전송")
                user.translation_queue.put(text)
                user.translated_queue.put(text)
                user.sentence_queue.task_done()
                continue

            # 번역 API 호출 (예시: GPT-4o-mini 번역 요청)
            try:
                source_name = language_map.get(source_lang, "감지된 언어")
                target_name = language_map.get(user.target_lang)
                response = CLIENT.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"Translate the following text from {source_name} to {target_name}. Only provide the translation without any additional explanation."},
                        {"role": "user", "content": text}
                    ]
                )
                translation = response.choices[0].message.content.strip()
                print(f"[DEBUG] {user.name} 번역 결과: {translation}")
            except Exception as e:
                print(f"[DEBUG] {user.name} 번역 오류: {e}", file=sys.stderr)
                translation = ""
            
            if translation:
                # 로그 저장 (기존 get_log_filenames 함수 활용)
                _, target_log = get_log_filenames(source_lang, user.target_lang)
                try:
                    with open(target_log, "a", encoding="utf-8") as f:
                        f.write(translation + "\n")
                except Exception as log_e:
                    print(f"[DEBUG] {user.name} 로그 저장 오류: {log_e}", file=sys.stderr)
                # 사용자 전용 큐에 결과 저장
                user.translation_queue.put(translation)
                user.translated_queue.put(translation)
            user.sentence_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[DEBUG] {user.name} 번역 처리 중 오류 발생: {e}", file=sys.stderr)
            time.sleep(0.1)

def translation_process(user, text):
    """
    메시지를 받아 해당 메시지를 사용자의 target_lang으로 번역한 결과를
    user.translation_queue 및 user.translated_queue에 넣습니다.
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
        
    except Exception as e:
        print(f"[DEBUG] {user.name} 번역 처리 중 오류 발생: {e}", file=sys.stderr)
        return
