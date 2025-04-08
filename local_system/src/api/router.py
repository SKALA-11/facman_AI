from chatbot import ChatBot
from fastapi import APIRouter, UploadFile

router = APIRouter()
chatbot = ChatBot()

latest_file = ""
latest_explain = ""

@router.get("/problem_lists")
async def problem_lists():
    problems = [
        {"id":"id1", "type": "type1", "value": "value1", "time": "2000.09.25"},
        {"id":"id2", "type": "type2", "value": "value2", "time": "2000.09.25"},
        {"id":"id3", "type": "type3", "value": "value3", "time": "2000.09.25"},
        {"id":"id4", "type": "type4", "value": "value4", "time": "2000.09.25"},
        {"id":"id5", "type": "type5", "value": "value5", "time": "2000.09.25"},
    ]
    return {"problems": problems}

@router.post("/problem_complete")
async def problem_complete(problem_id):
    return {"problem_id":problem_id}

@router.post("/solve_problem")
async def solve_problem(problem_id, file: UploadFile, explain: str):
    latest_file = file
    latest_explain = explain
    answer = chatbot.solve_problem("불이 났다.", file, explain)
    return {"answer":answer}

@router.get("/download_report/{problem_id}")
async def get_report(problem_id: int):
    answer = chatbot.make_report_content("불이 났다.", latest_file, latest_explain)
    return {"answer":answer}
