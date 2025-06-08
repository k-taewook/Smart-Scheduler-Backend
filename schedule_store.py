from datetime import datetime, timedelta
from typing import List, Dict
from schemas import ParsedSchedule
import json

# 메모리 내 일정 저장소
schedules: List[Dict] = []

def check_schedule_conflict(new_schedule: dict) -> List[dict]:
    """새로운 일정과 기존 일정의 충돌을 체크"""
    conflicts = []
    new_start = datetime.fromisoformat(new_schedule["start_date_time"])
    new_end = datetime.fromisoformat(new_schedule["end_date_time"])
    
    for existing_schedule in schedules:
        existing_start = datetime.fromisoformat(existing_schedule["start_date_time"])
        existing_end = datetime.fromisoformat(existing_schedule["end_date_time"])
        
        # 시간이 겹치는지 확인
        if (new_start < existing_end and new_end > existing_start):
            conflicts.append(existing_schedule)
    
    return conflicts

def add_schedule(schedule: ParsedSchedule | Dict) -> None:
    """일정을 저장소에 추가"""
    if isinstance(schedule, dict):
        schedule_dict = schedule
    else:
        schedule_dict = schedule.dict()
    
    # 충돌 체크
    conflicts = check_schedule_conflict(schedule_dict)
    if conflicts:
        conflict_info = []
        for conflict in conflicts:
            conflict_info.append(f"{conflict['title']} : {conflict['start_date_time']} ~ {conflict['end_date_time']}")
        raise ValueError(f"일정 시간이 겹칩니다. {', '.join(conflict_info)}")
    
    # 반복 일정인 경우 반복 규칙에 따라 일정 생성
    if schedule_dict.get("is_recurring"):
        current_date = datetime.fromisoformat(schedule_dict["start_date_time"])
        # 반복 종료 날짜가 지정되지 않은 경우 3개월 후로 설정
        end_date = datetime.fromisoformat(schedule_dict.get("recurrence_end_date")) if schedule_dict.get("recurrence_end_date") else (datetime.now() + timedelta(days=90))
        
        # 시작 날짜가 현재 날짜보다 이전인 경우 현재 날짜로 조정
        if current_date < datetime.now():
            current_date = datetime.now()
        
        while current_date <= end_date:
            # 주간 반복인 경우 지정된 요일에만 일정 생성
            if schedule_dict.get("recurrence_rule") == "WEEKLY" and schedule_dict.get("recurrence_days"):
                # 현재 날짜의 요일이 지정된 요일 중 하나인지 확인
                current_day = current_date.strftime("%A").upper()
                if current_day not in schedule_dict["recurrence_days"]:
                    # 다음 날로 이동
                    current_date += timedelta(days=1)
                    continue
            
            # 일정 복사본 생성
            event_copy = schedule_dict.copy()
            event_copy["start_date_time"] = current_date.isoformat()
            event_copy["end_date_time"] = (current_date + (datetime.fromisoformat(schedule_dict["end_date_time"]) - datetime.fromisoformat(schedule_dict["start_date_time"]))).isoformat()
            event_copy["is_recurring"] = False  # 개별 일정으로 저장
            event_copy["recurrence_rule"] = None
            event_copy["recurrence_end_date"] = None
            event_copy["recurrence_days"] = None
            
            # 반복 일정의 각 인스턴스에 대해서도 충돌 체크
            conflicts = check_schedule_conflict(event_copy)
            if conflicts:
                raise ValueError("반복 일정의 일부가 기존 일정과 겹칩니다", conflicts)
            
            schedules.append(event_copy)
            
            # 다음 반복 일정 계산
            if schedule_dict.get("recurrence_rule") == "DAILY":
                current_date += timedelta(days=1)
            elif schedule_dict.get("recurrence_rule") == "WEEKLY":
                # 다음 주의 같은 요일로 이동
                current_date += timedelta(days=7)
            elif schedule_dict.get("recurrence_rule") == "MONTHLY":
                # 다음 달의 같은 날짜로 이동
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
            elif schedule_dict.get("recurrence_rule") == "YEARLY":
                current_date = current_date.replace(year=current_date.year + 1)
    else:
        # 일반 일정은 datetime을 문자열로 변환하여 저장
        if not isinstance(schedule, dict):
            schedule_dict["start_date_time"] = schedule.start_date_time.isoformat()
            schedule_dict["end_date_time"] = schedule.end_date_time.isoformat()
        schedules.append(schedule_dict)

def get_all_schedules() -> List[Dict]:
    """모든 일정 조회"""
    return schedules

def clear_schedules() -> None:
    """모든 일정 삭제"""
    schedules.clear()

async def delete_schedule(parsed_schedule: ParsedSchedule) -> int:
    """일정 삭제"""
    deleted_count = 0
    global schedules  # 전역 변수 사용
    
    print(f"삭제하려는 일정: {parsed_schedule.title}")
    print(f"현재 저장된 일정들: {schedules}")
    
    # 삭제할 일정 찾기
    for schedule in schedules[:]:  # 복사본으로 순회
        print(f"비교 중인 일정: {schedule['title']}")
        
        # 제목이 일치하는 경우 삭제
        if schedule["title"] == parsed_schedule.title:
            print(f"일치하는 일정 발견: {schedule['title']}")
            schedules.remove(schedule)
            deleted_count += 1
    
    print(f"삭제된 일정 수: {deleted_count}")
    return deleted_count
