# Smart Scheduler Backend

FastAPI 기반의 일정 관리 백엔드입니다. 자연어 문장을 Gemini API로 파싱해 일정을 저장하고, 저장된 일정의 조회/삭제/일정 요약/패턴 분석을 제공합니다. 현재 구현은 메모리 기반 저장소를 사용하므로 서버를 재시작하면 일정이 초기화됩니다.

## 주요 기능

- 자연어 일정 파싱: `Gemini`를 사용해 입력 문장에서 일정 제목, 시작/종료 시간, 카테고리, 반복 규칙, 삭제 여부를 추출합니다.
- 일정 저장/조회/삭제: 메모리 저장소에 일정을 추가하고 목록을 조회하거나 삭제할 수 있습니다.
- 반복 일정 지원: `DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY` 규칙을 처리합니다.
- 충돌 감지: 새 일정이 기존 일정과 시간이 겹치면 충돌로 판단합니다.
- 주간 요약: 이번 주 일정 수, 총 소요 시간, 가장 바쁜 요일, 자유 시간대를 계산합니다.
- 패턴 분석: 자주 등장하는 시작 시간과 평균 일정 길이를 분석하고 개선 제안을 제공합니다.
- 간단한 로그인 API: 현재는 `hong / 1234` 하드코딩 인증만 제공합니다.

## 기술 스택

- Python 3.x
- FastAPI
- Uvicorn
- Pydantic v2
- python-dotenv
- google-generativeai

## 프로젝트 구조

```text
main.py             # FastAPI 엔트리포인트 및 API 라우트
gemini_parser.py    # Gemini를 이용한 자연어 일정 파싱
schedule_store.py   # 메모리 기반 일정 저장, 충돌 검사, 삭제
schemas.py          # 요청/응답 Pydantic 모델
requirements.txt    # 의존성 목록
README.md           # 프로젝트 문서
```

## 사전 준비

1. Python 3.10 이상을 권장합니다.
2. Google Gemini API 키가 필요합니다.
3. 프론트엔드가 다른 도메인에서 호출할 경우 CORS 허용 목록에 맞는 주소가 필요합니다.

## 설치

가상환경을 만든 뒤 의존성을 설치합니다.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 환경 변수

프로젝트 루트에 `.env` 파일을 만들고 Gemini API 키를 설정합니다.

```env
GOOGLE_API_KEY=your_google_gemini_api_key
```

`gemini_parser.py`는 실행 시 이 값을 읽어 `google-generativeai`를 초기화합니다.

## 실행

개발 서버를 실행합니다.

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

브라우저에서 다음 주소를 확인할 수 있습니다.

- API 확인: `http://localhost:8000/`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API 요약

### `GET /`

서버 상태 확인용 엔드포인트입니다.

응답 예시:

```json
{
	"message": "Smart Scheduler Backend API is running"
}
```

### `POST /login`

간단한 로그인 API입니다. 현재는 아래 계정만 성공합니다.

- `username`: `hong`
- `password`: `1234`

요청 예시:

```json
{
	"username": "hong",
	"password": "1234"
}
```

### `POST /parse_schedule`

자연어 문장을 받아 일정으로 파싱하고, 삭제 요청이면 삭제를 수행합니다. 삭제 요청이 아니면 파싱된 일정을 저장합니다.

요청 본문:

```json
{
	"text": "내일 오후 3시부터 4시까지 팀 미팅"
}
```

동작:

- 문장에 `삭제`, `지우`, `취소`가 포함되면 삭제 명령으로 해석합니다.
- 그 외에는 Gemini가 JSON 형식의 일정 정보를 추출합니다.
- 파싱 결과의 `title`, `start_date_time`, `end_date_time`를 저장합니다.

### `GET /schedules`

저장된 모든 일정을 반환합니다.

### `POST /delete_schedule`

자연어 문장을 파싱한 뒤 제목이 일치하는 일정을 삭제합니다.

요청 예시:

```json
{
	"text": "팀 미팅 삭제"
}
```

### `POST /delete_all_schedules`

저장된 모든 일정을 삭제합니다.

### `POST /schedules`

여러 일정을 한 번에 저장합니다. 요청이 들어오면 기존 일정을 모두 삭제한 뒤, 전달된 목록을 다시 저장합니다.

요청 예시:

```json
[
	{
		"content": "팀 미팅",
		"start": "2026-08-05T15:00:00",
		"end": "2026-08-05T16:00:00"
	},
	{
		"content": "운동",
		"start": "2026-08-05T18:00:00",
		"end": "2026-08-05T19:00:00"
	}
]
```

충돌이 발생하면 `409 Conflict`를 반환합니다.

### `GET /weekly_summary`

이번 주 일정의 요약 정보를 반환합니다.

반환 값:

- `total_schedules`: 이번 주 일정 개수
- `total_hours`: 총 일정 시간
- `busiest_day`: 가장 바쁜 요일
- `free_time_slots`: 비어 있는 시간대 목록

### `GET /schedule_patterns`

전체 일정의 패턴을 분석해 자주 등장하는 시작 시간, 평균 일정 길이, 개선 제안을 반환합니다.

## 일정 데이터 형식

내부적으로 일정은 다음 필드를 사용합니다.

```json
{
	"title": "팀 미팅",
	"start_date_time": "2026-08-05T15:00:00",
	"end_date_time": "2026-08-05T16:00:00",
	"category": "미팅",
	"is_recurring": false,
	"recurrence_rule": null,
	"recurrence_days": null,
	"recurrence_end_date": null,
	"is_delete": false
}
```

반복 일정이면 `is_recurring`이 `true`가 되며, 저장 시 각 인스턴스로 펼쳐집니다.

## 구현 메모

- 저장소는 DB가 아니라 메모리 리스트입니다. 영속성이 필요하면 별도 저장소를 붙여야 합니다.
- Gemini 응답은 JSON 문자열이어야 하며, 코드에서는 불필요한 마크다운 마커를 제거한 뒤 파싱합니다.
- 카테고리는 제목의 키워드에 따라 `미팅`, `수업`, `개인`, `기타`로 정리됩니다.
- CORS 허용 도메인은 `http://localhost:8080`, `https://smart-scheduler-frontend.vercel.app`, `https://smart-scheduler-backend-production.up.railway.app` 입니다.

## 참고

이 프로젝트는 현재 구현 기준으로 작성되었습니다. 일정 저장 방식, 인증, 반복 규칙 처리, 충돌 검사 로직을 바꾸면 README의 API 설명도 함께 갱신하는 것이 좋습니다.