# modules/translation.py

import queue, time
import openai
from modules.utils import language_map, get_log_filenames
from config import CLIENT
import sys

# def translation_thread(sentence_queue, translation_queue, translated_queue, target_language):
#     while True:
#         try:
#             sentence_data = sentence_queue.get(timeout=1)
#             if isinstance(sentence_data, tuple):
#                 sentence, source_lang = sentence_data
#             else:
#                 sentence = sentence_data
#                 source_lang = "ko"
#             print(f"[DEBUG] 번역할 문장: {sentence} (소스 언어: {source_lang})")
#             if source_lang == target_language:
#                 print("[DEBUG] 소스 언어와 타겟 언어 동일, 번역 건너뜀")
#                 translation_queue.put(sentence)
#                 sentence_queue.task_done()
#                 continue
#             try:
#                 source_name = language_map.get(source_lang, "감지된 언어")
#                 target_name = language_map.get(target_language, "영어")
#                 response = CLIENT.chat.completions.create(
#                     model="gpt-4o-mini",
#                     messages=[
#                         {"role": "system", "content": f"Translate the following text from {source_name} to {target_name}. Only provide the translation without any additional explanation."},
#                         {"role": "user", "content": sentence}
#                     ]
#                 )
#                 translation = response.choices[0].message.content.strip()
#                 print(f"[DEBUG] 번역 결과: {translation}")
#             except Exception as e:
#                 print(f"번역 오류: {e}", file=sys.stderr)
#                 translation = ""
#             if translation:
#                 _, target_log = get_log_filenames(source_lang, target_language)
#                 with open(target_log, "a", encoding="utf-8") as f:
#                     f.write(translation + "\n")
#                 translation_queue.put(translation)
#                 translated_queue.put(translation)
#             sentence_queue.task_done()
#         except queue.Empty:
#             continue

def translation_thread(user):
    """
    사용자 객체의 sentence_queue에서 문장을 가져와 번역을 수행하고,
    번역 결과를 user.translation_queue 및 user.translated_queue에 넣습니다.
    """
    while True:
        try:
            # user.sentence_queue에 (sentence, source_lang) 형태의 데이터가 들어있다고 가정
            sentence_data = user.sentence_queue.get(timeout=1)
            if isinstance(sentence_data, tuple):
                sentence, source_lang = sentence_data
            else:
                sentence = sentence_data
                source_lang = user.source_lang  # 기본값으로 사용자의 source_lang 사용

            print(f"[DEBUG] {user.name} 번역할 문장: {sentence} (소스 언어: {source_lang})")

            # 만약 소스 언어와 사용자의 target_lang이 같다면 번역하지 않고 원문 그대로 전달
            if source_lang == user.target_lang:
                print(f"[DEBUG] {user.name}: 소스 언어와 타겟 언어 동일, 번역 건너뜀")
                user.translation_queue.put(sentence)
                user.translated_queue.put(sentence)
                user.sentence_queue.task_done()
                continue

            # 번역 요청 전송
            try:
                source_name = language_map.get(source_lang, "감지된 언어")
                target_name = language_map.get(user.target_lang, "영어")
                response = CLIENT.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"Translate the following text from {source_name} to {target_name}. Only provide the translation without any additional explanation."},
                        {"role": "user", "content": sentence}
                    ]
                )
                translation = response.choices[0].message.content.strip()
                print(f"[DEBUG] {user.name} 번역 결과: {translation}")
            except Exception as e:
                print(f"[DEBUG] {user.name} 번역 오류: {e}", file=sys.stderr)
                translation = ""

            if translation:
                # 로그 파일에 번역 결과 기록
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
