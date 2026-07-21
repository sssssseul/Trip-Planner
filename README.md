# Trip Planner (Flask + PostgreSQL)

ClockOut과 같은 방식(Python/Flask)으로 만든 버전이에요. 화면(HTML/CSS/JS)은 이전 Express
버전과 완전히 동일하고, 서버만 Python으로 바뀌었어요.

## 폴더 구조

```
trip-planner-flask/
  app.py            Flask 서버 + API (ClockOut의 app.py 역할)
  requirements.txt  Python 패키지 목록
  schema.sql        테이블 정의 (서버 시작 시 자동 실행)
  public/
    index.html      화면
    app.js          API 호출 로직 (변경 없음)
```

## 로컬에서 실행해보기

```bash
python -m venv venv
source venv/bin/activate   # 윈도우는 venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # DATABASE_URL을 로컬 postgres 주소로 수정
python app.py
```

`http://localhost:3000` 접속. 테이블은 처음 뜰 때 자동으로 생겨요.

## GitHub에 올리기

이전에 하시던 방식 그대로예요.

1. 레포 페이지에서 **uploading an existing file**
2. 폴더 안 파일/폴더 전체 드래그 (`app.py`, `requirements.txt`, `schema.sql`, `render.yaml`,
   `README.md`, `public/` 등)
3. **Commit changes**

## Render 배포

1. render.com → **New +** → **PostgreSQL** 생성 → **Internal Database URL** 복사
2. **New +** → **Web Service** → 방금 올린 레포 연결
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Environment → `DATABASE_URL`에 1번 값 붙여넣기
3. **Create Web Service**

배포되면 서버가 뜰 때 `schema.sql`이 자동 실행돼서 테이블이 만들어져요. 마이그레이션 따로
돌릴 필요 없어요.

## 참고

- Express 버전과 API 엔드포인트가 완전히 동일해서, `public/index.html`과 `public/app.js`는
  손댈 필요가 없어요.
- 지금은 여행 1개만 관리하는 구조예요. 여러 여행을 관리하고 싶어지면 말씀해주세요.
