from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from schemas import NaturalLanguageInput, ParsedSchedule
from gemini_parser import parse_schedule_with_gemini
from schedule_store import add_schedule, get_all_schedules, delete_schedule, clear_schedules
from datetime import datetime, timedelta
import google.generativeai as genai
from typing import List, Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",  # 로컬 개발 환경
        "https://smart-scheduler-frontend.vercel.app",  # Vercel 배포 URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
def login(request: LoginRequest):
    if request.username == "hong" and request.password == "1234":
        return {"message": "로그인 성공"}
    raise HTTPException(status_code=401, detail="로그인 실패")
    
@app.post("/parse_schedule", response_model=ParsedSchedule)
def parse_schedule(input: NaturalLanguageInput):
    try:
        schedule = parse_schedule_with_gemini(input.text)
        print(f"파싱된 일정 데이터: {schedule}")
        
        if schedule.is_delete:
            # 일정 삭제
            deleted_count = delete_schedule(schedule)
            return {"message": f"{deleted_count}개의 일정이 삭제되었습니다."}
        else:
            # 일정 저장
            schedule_data = {
                "title": schedule.title,
                "start_date_time": schedule.start_date_time,
                "end_date_time": schedule.end_date_time
            }
            print(f"저장할 일정 데이터: {schedule_data}")
            add_schedule(schedule_data)
            
            return schedule
    except Exception as e:
        print(f"일정 파싱/저장 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/schedules", response_model=list[ParsedSchedule])
def list_schedules():
    return get_all_schedules()

@app.post("/delete_schedule")
async def delete_schedule_endpoint(input: NaturalLanguageInput):
    try:
        # 일정 파싱
        parsed = parse_schedule_with_gemini(input.text)
        
        # 일정 삭제
        deleted_count = await delete_schedule(parsed)
        
        return {"message": f"{deleted_count}개의 일정이 삭제되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/delete_all_schedules")
async def delete_all_schedules():
    try:
        # 모든 일정 삭제
        clear_schedules()  # schedule_store의 clear_schedules 함수 사용
        return {"message": "모든 일정이 삭제되었습니다."}
    except Exception as e:
        print(f"Delete all schedules error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class ScheduleConflict(BaseModel):
    existing_schedule: ParsedSchedule
    new_schedule: ParsedSchedule
    suggested_times: List[dict]

class WeeklySummary(BaseModel):
    total_schedules: int
    total_hours: float
    busiest_day: str
    free_time_slots: List[dict]
    category_summary: dict

@app.post("/schedules")
async def save_schedules(schedules: List[dict]):
    try:
        print(f"일정 저장 시작: {len(schedules)}개의 일정")
        print(f"저장할 일정 데이터: {schedules}")
        
        # 기존 일정 모두 삭제
        clear_schedules()
        
        # 새 일정 추가
        for schedule in schedules:
            try:
                schedule_data = {
                    "title": schedule["content"],
                    "start_date_time": schedule["start"],
                    "end_date_time": schedule["end"]
                }
                print(f"일정 추가 시도: {schedule_data}")
                try:
                    add_schedule(schedule_data)
                except ValueError as e:
                    if len(e.args) > 1 and isinstance(e.args[1], list):
                        # 충돌이 발생한 경우
                        conflicts = e.args[1]
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "message": "일정 시간이 겹칩니다",
                                "conflicts": conflicts
                            }
                        )
                    else:
                        raise
            except Exception as e:
                print(f"개별 일정 추가 중 오류: {str(e)}")
                continue
        
        # 저장된 일정 다시 가져오기
        saved_schedules = get_all_schedules()
        print(f"저장된 일정 수: {len(saved_schedules)}")
        print(f"저장된 일정 데이터: {saved_schedules}")
        
        return {"message": f"{len(saved_schedules)}개의 일정이 저장되었습니다."}
    except Exception as e:
        print(f"Save schedules error: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/weekly_summary")
async def get_weekly_summary():
    """주간 일정 요약"""
    try:
        schedules = get_all_schedules()  # 일정 목록 가져오기
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        # 이번 주 일정 필터링
        weekly_schedules = [
            s for s in schedules
            if start_of_week <= datetime.fromisoformat(s["start_date_time"]) <= end_of_week
        ]
        
        # 요일별 일정 수 계산
        schedules_by_day = {}
        day_mapping = {
            "Monday": "월",
            "Tuesday": "화",
            "Wednesday": "수",
            "Thursday": "목",
            "Friday": "금",
            "Saturday": "토",
            "Sunday": "일"
        }
        
        for schedule in weekly_schedules:
            day = datetime.fromisoformat(schedule["start_date_time"]).strftime("%A")
            korean_day = day_mapping[day]
            schedules_by_day[korean_day] = schedules_by_day.get(korean_day, 0) + 1
        
        # 가장 바쁜 날 찾기
        busiest_day = max(schedules_by_day.items(), key=lambda x: x[1])[0] if schedules_by_day else None
        if busiest_day:
            busiest_day = f"{busiest_day}요일 ({schedules_by_day[busiest_day]}개)"
        
        # 총 시간 계산
        total_hours = sum(
            (datetime.fromisoformat(s["end_date_time"]) - datetime.fromisoformat(s["start_date_time"])).total_seconds() / 3600
            for s in weekly_schedules
        )
        
        # 자유 시간대 계산
        free_time_slots = []
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            korean_day = day_mapping[day]
            day_schedules = [
                s for s in weekly_schedules
                if datetime.fromisoformat(s["start_date_time"]).strftime("%A") == day
            ]
            
            if not day_schedules:
                free_time_slots.append(f"{korean_day}요일 00:00~23:59")
                continue
            
            # 일정 시간 정렬
            day_schedules.sort(key=lambda x: datetime.fromisoformat(x["start_date_time"]))
            
            # 자유 시간대 찾기
            current_time = datetime.fromisoformat(day_schedules[0]["start_date_time"]).replace(hour=0, minute=0)
            for schedule in day_schedules:
                schedule_start = datetime.fromisoformat(schedule["start_date_time"])
                if current_time < schedule_start:
                    free_time_slots.append(
                        f"{korean_day}요일 {current_time.strftime('%H:%M')}~{schedule_start.strftime('%H:%M')}"
                    )
                current_time = datetime.fromisoformat(schedule["end_date_time"])
            
            # 마지막 일정 이후 시간
            if current_time < datetime.fromisoformat(day_schedules[-1]["end_date_time"]).replace(hour=23, minute=59):
                free_time_slots.append(
                    f"{korean_day}요일 {current_time.strftime('%H:%M')}~23:59"
                )
        
        return {
            "total_schedules": len(weekly_schedules),
            "total_hours": round(total_hours, 1),
            "busiest_day": busiest_day or "없음",
            "free_time_slots": free_time_slots
        }
    except Exception as e:
        print(f"Weekly summary error: {str(e)}")
        return {
            "total_schedules": 0,
            "total_hours": 0,
            "busiest_day": "오류 발생",
            "free_time_slots": []
        }

@app.get("/schedule_patterns")
async def get_schedule_patterns():
    """일정 패턴 분석"""
    try:
        schedules = get_all_schedules()  # 일정 목록 가져오기
        if not schedules:
            return {
                "common_schedule_time": "없음",
                "average_duration": "없음",
                "improvement_suggestions": ["일정이 없습니다."]
            }
        
        # 자주 있는 일정 시간 분석
        time_slots = {}
        for schedule in schedules:
            start_time = datetime.fromisoformat(schedule["start_date_time"]).strftime("%H:%M")
            time_slots[start_time] = time_slots.get(start_time, 0) + 1
        
        common_time = max(time_slots.items(), key=lambda x: x[1])[0] if time_slots else None
        if common_time:
            common_time = f"{common_time} ({time_slots[common_time]}개)"
        
        # 평균 일정 시간 계산
        total_duration = sum(
            (datetime.fromisoformat(s["end_date_time"]) - datetime.fromisoformat(s["start_date_time"])).total_seconds() / 3600
            for s in schedules
        )
        average_duration = round(total_duration / len(schedules), 1) if schedules else 0
        
        # 개선 제안
        suggestions = []
        if average_duration > 2:
            suggestions.append("일정 시간이 평균 2시간 이상입니다. 더 짧은 시간으로 나누는 것을 고려해보세요.")
        
        if len(schedules) > 10:
            suggestions.append("일정이 많습니다. 우선순위를 정하고 불필요한 일정은 제거하는 것이 좋습니다.")
        
        # 특정 시간대에 일정이 집중되어 있는지 확인
        max_schedules_at_time = max(time_slots.values()) if time_slots else 0
        if max_schedules_at_time > 3:
            time_with_most = max(time_slots.items(), key=lambda x: x[1])[0]
            suggestions.append(f"{time_with_most}에 일정이 집중되어 있습니다. 시간대를 분산하는 것이 좋습니다.")
        
        return {
            "common_schedule_time": common_time or "없음",
            "average_duration": f"{average_duration}시간",
            "improvement_suggestions": suggestions
        }
    except Exception as e:
        print(f"Schedule patterns error: {str(e)}")
        return {
            "common_schedule_time": "오류 발생",
            "average_duration": "0시간",
            "improvement_suggestions": ["일정 분석 중 오류가 발생했습니다"]
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)