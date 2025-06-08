import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from schemas import ParsedSchedule

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def parse_schedule_with_gemini(text: str) -> ParsedSchedule:
    # 삭제 명령어 확인
    is_delete_command = any(word in text for word in ["삭제", "지우", "취소"])
    
    # 현재 시간 기준으로 상대적인 날짜 처리
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    current_day = now.day

    # 다음 월요일 날짜 계산
    days_until_monday = (7 - now.weekday()) % 7
    next_monday = now + timedelta(days=days_until_monday)
    next_monday = next_monday.replace(hour=10, minute=0, second=0, microsecond=0)

    # 3개월 후 날짜 계산
    three_months_later = now + timedelta(days=90)

    prompt = f"""현재 시간은 {current_year}년 {current_month}월 {current_day}일입니다.
아래 문장에서 일정 정보를 추출해서 JSON 형식으로만 출력해줘.
입력 문장: "{text}"

다음 형식으로만 출력해줘 (다른 설명이나 텍스트는 포함하지 마세요):
{{
    "title": "일정명",
    "start_date_time": "YYYY-MM-DDTHH:MM:SS",
    "end_date_time": "YYYY-MM-DDTHH:MM:SS",
    "category": "미팅/수업/개인/기타",
    "is_recurring": true/false,
    "recurrence_rule": "DAILY/WEEKLY/MONTHLY/YEARLY" (반복 일정인 경우에만),
    "recurrence_end_date": "YYYY-MM-DD" (반복 일정인 경우에만),
    "recurrence_days": ["MONDAY", "WEDNESDAY"] (주간 반복인 경우에만),
    "is_delete": true/false (삭제 명령인 경우 true)
}}

주의사항:
1. 하루 종일 일정인 경우 시작 시간은 00:00:00, 종료 시간은 23:59:59로 설정
2. 여러 날짜의 일정인 경우 마지막 날짜의 종료 시간은 23:59:59로 설정
3. 반복 일정인 경우 is_recurring을 true로 설정하고 적절한 recurrence_rule 설정
4. 주간 반복인 경우 recurrence_days에 요일 목록 포함
5. 반복 종료 날짜가 명시되지 않은 경우, 현재 날짜로부터 3개월 후로 설정
6. 시작 날짜는 현재 날짜 이후로 설정 (과거 날짜 사용 금지)
7. 연도는 반드시 {current_year}년을 사용해야 함
8. 카테고리는 다음 규칙에 따라 자동으로 분류:
   - "미팅", "회의", "미팅" 등의 단어가 포함되면 "미팅"
   - "수업", "강의", "학습" 등의 단어가 포함되면 "수업"
   - "개인", "휴식", "운동" 등의 단어가 포함되면 "개인"
   - 그 외의 경우 "기타"

예시:
입력: "매주 월요일 오전 10시부터 12시까지 팀 미팅 삭제"
출력: {{
    "title": "팀 미팅",
    "start_date_time": "{next_monday.strftime('%Y-%m-%dT%H:%M:%S')}",
    "end_date_time": "{next_monday.replace(hour=12).strftime('%Y-%m-%dT%H:%M:%S')}",
    "category": "미팅",
    "is_recurring": true,
    "recurrence_rule": "WEEKLY",
    "recurrence_end_date": "{three_months_later.strftime('%Y-%m-%d')}",
    "recurrence_days": ["MONDAY"],
    "is_delete": true
}}

입력: "매일 오후 3시부터 4시까지 영어 공부, 6월 30일까지"
출력: {{
    "title": "영어 공부",
    "start_date_time": "{now.replace(hour=15, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M:%S')}",
    "end_date_time": "{now.replace(hour=16, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M:%S')}",
    "category": "수업",
    "is_recurring": true,
    "recurrence_rule": "DAILY",
    "recurrence_end_date": "{current_year}-06-30"
}}

입력: "5월 10일 15시부터 17시까지 팀 미팅 삭제"
출력: {{
    "title": "팀 미팅",
    "start_date_time": "{current_year}-05-10T15:00:00",
    "end_date_time": "{current_year}-05-10T17:00:00",
    "category": "미팅",
    "is_recurring": false,
    "is_delete": true
}}
"""

    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content(prompt)
    result = response.text.strip()
    
    print("Gemini API 응답:", result)

    try:
        # JSON 문자열에서 불필요한 문자 제거
        result = result.replace("```json", "").replace("```", "").strip()
        
        # 입력/출력 형식의 텍스트가 포함된 경우 제거
        if "입력:" in result:
            result = result.split("출력:")[-1].strip()
        
        parsed = json.loads(result)
        
        # 날짜 유효성 검사
        start_date = datetime.fromisoformat(parsed["start_date_time"])
        if start_date.year != current_year:
            # 연도가 현재 연도가 아닌 경우 현재 연도로 수정
            start_date = start_date.replace(year=current_year)
            parsed["start_date_time"] = start_date.strftime("%Y-%m-%dT%H:%M:%S")
            
            if parsed.get("recurrence_end_date"):
                end_date = datetime.fromisoformat(parsed["recurrence_end_date"])
                end_date = end_date.replace(year=current_year)
                parsed["recurrence_end_date"] = end_date.strftime("%Y-%m-%d")
        
        print("파싱된 데이터:", parsed)
        
        # 필수 필드 확인
        if "title" not in parsed or "start_date_time" not in parsed or "end_date_time" not in parsed:
            raise ValueError("응답에 필수 필드가 없습니다")
        
        # 카테고리 자동 분류
        category = parsed.get("category", "기타")
        title_lower = parsed["title"].lower()
        
        if any(word in title_lower for word in ["미팅", "회의", "미팅"]):
            category = "미팅"
        elif any(word in title_lower for word in ["수업", "강의", "학습", "공부"]):
            category = "수업"
        elif any(word in title_lower for word in ["개인", "휴식", "운동", "취미"]):
            category = "개인"
            
        return ParsedSchedule(
            title=parsed["title"],
            start_date_time=datetime.fromisoformat(parsed["start_date_time"]).strftime("%Y-%m-%dT%H:%M:%S"),
            end_date_time=datetime.fromisoformat(parsed["end_date_time"]).strftime("%Y-%m-%dT%H:%M:%S"),
            category=category,
            is_recurring=parsed.get("is_recurring", False),
            recurrence_rule=parsed.get("recurrence_rule"),
            recurrence_end_date=datetime.fromisoformat(parsed["recurrence_end_date"]).strftime("%Y-%m-%d") if parsed.get("recurrence_end_date") else None,
            recurrence_days=parsed.get("recurrence_days"),
            is_delete=parsed.get("is_delete", False)
        )
    except json.JSONDecodeError as e:
        print("JSON 파싱 오류:", e)
        raise ValueError(f"JSON 파싱 실패: {e}")
    except Exception as e:
        print("일반 오류:", e)
        raise ValueError(f"일정 파싱 실패: {e}") 