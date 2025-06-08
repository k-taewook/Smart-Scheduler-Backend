from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class NaturalLanguageInput(BaseModel):
    text: str

class ParsedSchedule(BaseModel):
    title: str
    start_date_time: str
    end_date_time: str
    category: Optional[str] = "기타"  # 기본값은 "기타"
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    recurrence_days: Optional[List[str]] = None
    recurrence_end_date: Optional[str] = None
    is_delete: bool = False
