# Trip Planner

Express + PostgreSQL로 만든 여행 계획 웹 서비스예요. 체크리스트, 요일별 일정, 메인 이벤트를
전부 DB에 저장하고, 여러 사람이 같은 링크로 접속해도 항상 최신 상태를 보게 돼요.

## 폴더 구조

```
trip-planner-app/
  server.js        Express 서버 + REST API
  db.js             PostgreSQL 커넥션 풀
  schema.sql        테이블 정의 (서버 시작 시 자동 실행)
  public/
    index.html      화면
    app.js          API 호출 로직
```

## 로컬에서 실행해보기

1. PostgreSQL이 로컬에 있다면 데이터베이스를 하나 만들어요.
   ```
   createdb trip_planner
   ```
2. 의존성 설치
   ```
   npm install
   ```
3. `.env.example`을 `.env`로 복사하고 `DATABASE_URL`을 본인 환경에 맞게 수정해요.
4. 서버 실행
   ```
   npm start
   ```
5. 브라우저에서 `http://localhost:3000` 접속. 테이블은 서버가 처음 뜰 때 자동으로 만들어져요.

## Render에 배포하기

### 방법 A: render.yaml로 한 번에 (Blueprint)

1. 이 폴더를 GitHub 저장소에 올려요 (ClockOut, 둘이서 오늘의 카드 때와 동일한 방식).
2. Render 대시보드 → **New** → **Blueprint** → 방금 올린 저장소 선택.
3. `render.yaml`을 자동으로 읽어서 PostgreSQL 데이터베이스(`trip-planner-db`)와
   웹 서비스(`trip-planner`)를 같이 만들어줘요. `DATABASE_URL`도 자동으로 연결돼요.
4. 배포가 끝나면 나오는 `https://trip-planner-xxxx.onrender.com` 주소로 접속.

### 방법 B: 수동으로

1. Render 대시보드 → **New** → **PostgreSQL** 로 DB 먼저 생성. 생성 후 **Internal Database URL**을 복사해둬요.
2. **New** → **Web Service** → GitHub 저장소 연결.
   - Build Command: `npm install`
   - Start Command: `npm start`
3. 서비스의 **Environment** 탭에서 환경변수 추가:
   - `DATABASE_URL` = 1번에서 복사한 Internal Database URL
   - `NODE_ENV` = `production`
4. Deploy. 첫 실행 시 `schema.sql`이 자동으로 실행돼서 테이블이 만들어져요.

## 참고

- 무료 플랜 DB는 일정 기간 미사용 시 만료될 수 있어요. 계속 쓰실 거면 Render 대시보드에서
  DB 플랜/만료 정책을 확인해보세요.
- 지금은 여행을 1개만 관리하는 구조예요 (앱을 열면 항상 같은 여행이 보여요). 나중에
  "여행 목록" 기능이 필요하면 말씀해주세요 — trips 테이블은 이미 다중 여행을 지원할 수
  있게 만들어놔서 확장하기 어렵지 않아요.
- 시작일/종료일을 바꾸면 그 범위 밖에 있던 일정은 화면에서 안 보이지만 DB에서 삭제되진
  않아요. 다시 날짜 범위를 넓히면 그대로 돌아와요.
