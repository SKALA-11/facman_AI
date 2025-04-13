# modules/translation.py

import queue
import openai
from modules.utils import language_map, get_log_filenames
from config import CLIENT
import sys

def translation_thread(sentence_queue, translation_queue, translated_queue, target_language):
    while True:
        try:
            sentence_data = sentence_queue.get(timeout=1)
            if isinstance(sentence_data, tuple):
                sentence, source_lang = sentence_data
            else:
                sentence = sentence_data
                source_lang = "ko"
            print(f"[DEBUG] 번역할 문장: {sentence} (소스 언어: {source_lang})")
            if source_lang == target_language:
                print("[DEBUG] 소스 언어와 타겟 언어 동일, 번역 건너뜀")
                translation_queue.put(sentence)
                sentence_queue.task_done()
                continue
            try:
                source_name = language_map.get(source_lang, "감지된 언어")
                target_name = language_map.get(target_language, "영어")
                response = CLIENT.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"Translate the following text from {source_name} to {target_name}. Only provide the translation without any additional explanation."},
                        {"role": "user", "content": sentence}
                    ]
                )
                translation = response.choices[0].message.content.strip()
                print(f"[DEBUG] 번역 결과: {translation}")
            except Exception as e:
                print(f"번역 오류: {e}", file=sys.stderr)
                translation = ""
            if translation:
                _, target_log = get_log_filenames(source_lang, target_language)
                with open(target_log, "a", encoding="utf-8") as f:
                    f.write(translation + "\n")
                translation_queue.put(translation)
                translated_queue.put(translation)
            sentence_queue.task_done()
        except queue.Empty:
            continue