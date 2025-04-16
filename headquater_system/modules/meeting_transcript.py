# modules/meeting_transcript.py
import os
import json
import asyncio
from datetime import datetime
from config import CLIENT

# Define the log directory
LOG_DIR = "/home/ubuntu/meeting_logs"
os.makedirs(LOG_DIR, exist_ok=True)

async def save_transcript_entry(user_name, transcription, translation, session_id, timestamp=None):
    """
    Save a single transcript entry to the JSON file
    """
    if timestamp is None:
        timestamp = datetime.now().isoformat()
        
    try:
        # Use sessionId for organizing logs
        session_dir = os.path.join(LOG_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        log_file_path = os.path.join(session_dir, "transcript.json")
        
        # Read existing file if it exists
        transcript_data = []
        if os.path.exists(log_file_path):
            try:
                with open(log_file_path, "r", encoding="utf-8") as log_file:
                    transcript_data = json.load(log_file)
            except json.JSONDecodeError:
                # File is corrupted, start fresh
                transcript_data = []
        
        # Add new message
        transcript_data.append({
            "speaker": user_name,
            "transcription": transcription,
            "translation": translation,
            "timestamp": timestamp
        })
        
        # Save to file
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            json.dump(transcript_data, log_file, ensure_ascii=False, indent=2)
        
        print(f"[DEBUG] {user_name} JSON log entry saved (Session ID: {session_id})")
        return True
    except Exception as e:
        print(f"[DEBUG] Error saving transcript entry: {e}")
        return False

async def generate_meeting_summary(session_id):
    """
    Generate a meeting summary using OpenAI API
    """
    try:
        # Check if transcript exists
        session_dir = os.path.join(LOG_DIR, session_id)
        log_file_path = os.path.join(session_dir, "transcript.json")
        
        if not os.path.exists(log_file_path):
            return {"error": f"No transcript found for session ID: {session_id}"}, 404
        
        # Read transcript data
        with open(log_file_path, "r", encoding="utf-8") as log_file:
            transcript_data = json.load(log_file)
        
        if not transcript_data:
            return {"error": "Transcript is empty"}, 404
        
        # Get meeting date from first entry timestamp
        meeting_date = "Unknown date"
        if transcript_data and "timestamp" in transcript_data[0]:
            try:
                timestamp = datetime.fromisoformat(transcript_data[0]["timestamp"])
                meeting_date = timestamp.strftime("%Y년 %m월 %d일")
            except (ValueError, TypeError):
                pass
        
        # Get unique participants
        participants = list(set(entry["speaker"] for entry in transcript_data))
        
        # Format transcript for OpenAI
        formatted_transcript = ""
        for entry in transcript_data:
            formatted_transcript += f"{entry['speaker']}: {entry['transcription']}\n"
        
        # Generate summary using OpenAI API via CLIENT
        system_prompt = """
        당신은 회의 내용을 요약하는 전문가입니다. 다음 형식에 맞춰 회의 내용을 요약해주세요:

        # 회의 요약

        ## 기본 정보
        - 날짜: {date}
        - 참가자: {participants}
        - 회의 안건: [회의 안건을 파악하여 작성]

        ## 회의 주제
        [회의 주제를 파악하여 작성. 여러 주제가 있는 경우 구분하여 작성]

        ## 회의 내용
        [회의 중 오고 갔던 내용 중 중요한 내용을 정리해 작성.
        내용을 주제별로 분류하여 작성하며, 주제는 **볼드체**로 표시]

        ## 주요 의사 결정 사항
        [회의를 통해 결정된 사항 정리]

        ## Action Items
        [누가, 언제, 무엇을 해야하는지 명확하게 작성]
        """
        
        user_prompt = f"""
        다음은 회의 대화 내용입니다. 위 형식에 맞게 요약해주세요.
        날짜: {meeting_date}
        참가자: {', '.join(participants)}
        
        대화 내용:
        {formatted_transcript}
        """
        
        try:
            response = await CLIENT.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            summary = response.choices[0].message.content
            
            # Save summary to file
            summary_file_path = os.path.join(session_dir, "summary.json")
            summary_data = {
                "session_id": session_id,
                "summary": summary,
                "generated_at": datetime.now().isoformat(),
                "transcript_entries": len(transcript_data),
                "participants": participants,
                "meeting_date": meeting_date
            }
            
            with open(summary_file_path, "w", encoding="utf-8") as summary_file:
                json.dump(summary_data, summary_file, ensure_ascii=False, indent=2)
            
            return summary_data, 200
        except Exception as api_error:
            print(f"OpenAI API error: {api_error}")
            return {"error": f"OpenAI API error: {str(api_error)}"}, 500
    
    except Exception as e:
        print(f"Error generating meeting summary: {e}")
        return {"error": f"Failed to generate meeting summary: {str(e)}"}, 500

async def list_meeting_transcripts():
    """
    List all available meeting transcripts
    """
    try:
        if not os.path.exists(LOG_DIR):
            return {"transcripts": []}, 200
        
        sessions = []
        for session_id in os.listdir(LOG_DIR):
            session_dir = os.path.join(LOG_DIR, session_id)
            if not os.path.isdir(session_dir):
                continue
                
            transcript_path = os.path.join(session_dir, "transcript.json")
            if not os.path.exists(transcript_path):
                continue
                
            # Get basic info about the transcript
            try:
                with open(transcript_path, "r", encoding="utf-8") as f:
                    transcript_data = json.load(f)
                    
                # Get first and last timestamp to determine meeting duration
                first_entry = transcript_data[0] if transcript_data else {}
                last_entry = transcript_data[-1] if transcript_data else {}
                
                # Check if summary exists
                summary_path = os.path.join(session_dir, "summary.json")
                has_summary = os.path.exists(summary_path)
                
                sessions.append({
                    "session_id": session_id,
                    "entries_count": len(transcript_data),
                    "participants": list(set(entry["speaker"] for entry in transcript_data)),
                    "start_time": first_entry.get("timestamp", ""),
                    "end_time": last_entry.get("timestamp", ""),
                    "has_summary": has_summary
                })
            except Exception as e:
                print(f"Error processing transcript {session_id}: {e}")
                continue
        
        return {"transcripts": sessions}, 200
    
    except Exception as e:
        print(f"Error listing transcripts: {e}")
        return {"error": f"Failed to list transcripts: {str(e)}"}, 500

async def get_meeting_transcript(session_id):
    """
    Get a specific meeting transcript by session ID
    """
    try:
        session_dir = os.path.join(LOG_DIR, session_id)
        transcript_path = os.path.join(session_dir, "transcript.json")
        
        if not os.path.exists(transcript_path):
            return {"error": f"No transcript found for session ID: {session_id}"}, 404
            
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript_data = json.load(f)
            
        return {"transcript": transcript_data}, 200
    
    except Exception as e:
        print(f"Error retrieving transcript: {e}")
        return {"error": f"Failed to retrieve transcript: {str(e)}"}, 500

async def get_meeting_summary(session_id):
    """
    Get an existing meeting summary
    """
    try:
        session_dir = os.path.join(LOG_DIR, session_id)
        summary_path = os.path.join(session_dir, "summary.json")
        
        if not os.path.exists(summary_path):
            return {"error": f"No summary found for session ID: {session_id}"}, 404
            
        with open(summary_path, "r", encoding="utf-8") as f:
            summary_data = json.load(f)
            
        return summary_data, 200
    
    except Exception as e:
        print(f"Error retrieving summary: {e}")
        return {"error": f"Failed to retrieve summary: {str(e)}"}, 500