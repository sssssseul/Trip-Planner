import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
if not os.environ.get('SECRET_KEY'):
    print('경고: SECRET_KEY 환경변수가 없어서 임시 키를 씁니다. 서버가 재시작되면 '
          '모든 로그인이 풀려요. Render 환경변수에 SECRET_KEY를 추가해주세요.')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_URL = os.environ.get('DATABASE_URL')


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = f.read()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(schema)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM app_settings ORDER BY id LIMIT 1')
            row = cur.fetchone()
            if not row:
                cur.execute(
                    'INSERT INTO app_settings (trips_title) VALUES (%s)',
                    ('내 여행들',)
                )
                conn.commit()
    finally:
        conn.close()


def date_range(start_str, end_str):
    start = datetime.strptime(start_str, '%Y-%m-%d').date()
    end = datetime.strptime(end_str, '%Y-%m-%d').date()
    if end < start:
        return [start_str]
    days = []
    cur = start
    while cur <= end:
        days.append(cur.isoformat())
        cur += timedelta(days=1)
    return days


def login_required_page(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper


def login_required_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'login_required'}), 401
        return f(*args, **kwargs)
    return wrapper


def owns_trip(cur, trip_id, user_id):
    cur.execute('SELECT id FROM trips WHERE id = %s AND user_id = %s', (trip_id, user_id))
    return cur.fetchone() is not None


def owns_checklist_item(cur, item_id, user_id):
    cur.execute(
        'SELECT ci.id FROM checklist_items ci JOIN trips t ON t.id = ci.trip_id '
        'WHERE ci.id = %s AND t.user_id = %s',
        (item_id, user_id)
    )
    return cur.fetchone() is not None


def owns_itinerary_item(cur, item_id, user_id):
    cur.execute(
        'SELECT ii.id FROM itinerary_items ii JOIN trips t ON t.id = ii.trip_id '
        'WHERE ii.id = %s AND t.user_id = %s',
        (item_id, user_id)
    )
    return cur.fetchone() is not None


# ---------- 화면 ----------

@app.route('/')
def root():
    if session.get('user_id'):
        return redirect('/trips')
    return redirect('/login')


@app.route('/login')
def login_page():
    if session.get('user_id'):
        return redirect('/trips')
    return send_from_directory(BASE_DIR, 'auth.html')


@app.route('/signup')
def signup_page():
    if session.get('user_id'):
        return redirect('/trips')
    return send_from_directory(BASE_DIR, 'auth.html')


@app.route('/auth.js')
def auth_js():
    return send_from_directory(BASE_DIR, 'auth.js')


@app.route('/trips')
@login_required_page
def trips_page():
    return send_from_directory(BASE_DIR, 'trips.html')


@app.route('/trips.js')
def trips_js():
    return send_from_directory(BASE_DIR, 'trips.js')


@app.route('/account')
@login_required_page
def account_page():
    return send_from_directory(BASE_DIR, 'account.html')


@app.route('/account.js')
def account_js():
    return send_from_directory(BASE_DIR, 'account.js')


@app.route('/trip/<int:trip_id>')
@login_required_page
def trip_page(trip_id):
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/app.js')
def app_js():
    return send_from_directory(BASE_DIR, 'app.js')


# ---------- auth API ----------

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json(force=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if len(username) < 2:
        return jsonify({'error': '아이디는 2자 이상이어야 해요.'}), 400
    if len(password) < 6:
        return jsonify({'error': '비밀번호는 6자 이상이어야 해요.'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM users LIMIT 1')
            is_first_user = cur.fetchone() is None

            cur.execute('SELECT id FROM users WHERE username = %s', (username,))
            if cur.fetchone():
                return jsonify({'error': '이미 있는 아이디예요.'}), 400

            password_hash = generate_password_hash(password)
            cur.execute(
                'INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id',
                (username, password_hash)
            )
            new_user_id = cur.fetchone()['id']

            if is_first_user:
                # 로그인 기능이 생기기 전부터 있던 여행/설정을 첫 가입자에게 넘겨줘요.
                cur.execute(
                    'UPDATE trips SET user_id = %s WHERE user_id IS NULL',
                    (new_user_id,)
                )
                cur.execute(
                    'UPDATE app_settings SET user_id = %s WHERE user_id IS NULL',
                    (new_user_id,)
                )
        conn.commit()
        session.permanent = True
        session['user_id'] = new_user_id
        session['username'] = username
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': '가입에 실패했어요. 다시 시도해주세요.'}), 500
    finally:
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(force=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, password_hash FROM users WHERE username = %s', (username,))
            user = cur.fetchone()
        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({'error': '아이디 또는 비밀번호가 맞지 않아요.'}), 401
        session.permanent = True
        session['user_id'] = user['id']
        session['username'] = username
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': '로그인에 실패했어요. 다시 시도해주세요.'}), 500
    finally:
        conn.close()


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/me', methods=['GET'])
def me():
    if not session.get('user_id'):
        return jsonify({'error': 'login_required'}), 401
    return jsonify({'username': session.get('username')})


@app.route('/api/account/username', methods=['PUT'])
@login_required_api
def change_username():
    user_id = session['user_id']
    data = request.get_json(force=True) or {}
    new_username = (data.get('newUsername') or '').strip()
    password = data.get('password') or ''
    if len(new_username) < 2:
        return jsonify({'error': '아이디는 2자 이상이어야 해요.'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT password_hash FROM users WHERE id = %s', (user_id,))
            user = cur.fetchone()
            if not user or not check_password_hash(user['password_hash'], password):
                return jsonify({'error': '현재 비밀번호가 맞지 않아요.'}), 401

            cur.execute('SELECT id FROM users WHERE username = %s AND id != %s', (new_username, user_id))
            if cur.fetchone():
                return jsonify({'error': '이미 있는 아이디예요.'}), 400

            cur.execute('UPDATE users SET username = %s WHERE id = %s', (new_username, user_id))
        conn.commit()
        session['username'] = new_username
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': '변경에 실패했어요. 다시 시도해주세요.'}), 500
    finally:
        conn.close()


@app.route('/api/account/password', methods=['PUT'])
@login_required_api
def change_password():
    user_id = session['user_id']
    data = request.get_json(force=True) or {}
    current_password = data.get('currentPassword') or ''
    new_password = data.get('newPassword') or ''
    if len(new_password) < 6:
        return jsonify({'error': '새 비밀번호는 6자 이상이어야 해요.'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT password_hash FROM users WHERE id = %s', (user_id,))
            user = cur.fetchone()
            if not user or not check_password_hash(user['password_hash'], current_password):
                return jsonify({'error': '현재 비밀번호가 맞지 않아요.'}), 401

            new_hash = generate_password_hash(new_password)
            cur.execute('UPDATE users SET password_hash = %s WHERE id = %s', (new_hash, user_id))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': '변경에 실패했어요. 다시 시도해주세요.'}), 500
    finally:
        conn.close()


# ---------- app settings ----------

@app.route('/api/settings', methods=['GET'])
@login_required_api
def get_settings():
    user_id = session['user_id']
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT trips_title FROM app_settings WHERE user_id = %s LIMIT 1',
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                # 로그인 기능 붙이기 전부터 있던(주인 없는) 설정이 있으면 넘겨받아요.
                cur.execute('SELECT id, trips_title FROM app_settings WHERE user_id IS NULL LIMIT 1')
                orphan = cur.fetchone()
                if orphan:
                    cur.execute(
                        'UPDATE app_settings SET user_id = %s WHERE id = %s',
                        (user_id, orphan['id'])
                    )
                    conn.commit()
                    row = orphan
        return jsonify({'tripsTitle': row['trips_title'] if row else '내 여행들'})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


@app.route('/api/settings', methods=['PUT'])
@login_required_api
def update_settings():
    user_id = session['user_id']
    data = request.get_json(force=True) or {}
    trips_title = (data.get('tripsTitle') or '').strip()
    if not trips_title:
        return jsonify({'error': 'title_required'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM app_settings WHERE user_id = %s LIMIT 1', (user_id,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    'UPDATE app_settings SET trips_title = %s WHERE id = %s',
                    (trips_title, row['id'])
                )
            else:
                cur.execute(
                    'INSERT INTO app_settings (trips_title, user_id) VALUES (%s, %s)',
                    (trips_title, user_id)
                )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


# ---------- trips list ----------

@app.route('/api/trips', methods=['GET'])
@login_required_api
def list_trips():
    user_id = session['user_id']
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id, title, start_date, end_date, description FROM trips '
                'WHERE user_id = %s ORDER BY id ASC',
                (user_id,)
            )
            trips = cur.fetchall()
            result = [{
                'id': t['id'],
                'title': t['title'],
                'startDate': t['start_date'],
                'endDate': t['end_date'],
                'description': t['description'] or '',
            } for t in trips]
        return jsonify(result)
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


@app.route('/api/trips', methods=['POST'])
@login_required_api
def create_trip():
    user_id = session['user_id']
    data = request.get_json(force=True) or {}
    title = (data.get('title') or '').strip() or '새 여행'
    today = datetime.now().date().isoformat()
    start_date = data.get('startDate') or today
    end_date = data.get('endDate') or start_date
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO trips (title, start_date, end_date, user_id) VALUES (%s, %s, %s, %s) '
                'RETURNING id',
                (title, start_date, end_date, user_id)
            )
            new_id = cur.fetchone()['id']
        conn.commit()
        return jsonify({'id': new_id})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


@app.route('/api/trips/<int:trip_id>', methods=['DELETE'])
@login_required_api
def delete_trip(trip_id):
    user_id = session['user_id']
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not owns_trip(cur, trip_id, user_id):
                return jsonify({'error': 'not_found'}), 404
            cur.execute('DELETE FROM trips WHERE id = %s', (trip_id,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


# ---------- single trip ----------

@app.route('/api/trips/<int:trip_id>', methods=['GET'])
@login_required_api
def get_trip(trip_id):
    user_id = session['user_id']
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM trips WHERE id = %s AND user_id = %s', (trip_id, user_id))
            trip = cur.fetchone()
            if not trip:
                return jsonify({'error': 'not_found'}), 404

            cur.execute(
                'SELECT id, text, done FROM checklist_items WHERE trip_id = %s ORDER BY sort_order, id',
                (trip_id,)
            )
            checklist = cur.fetchall()

            cur.execute(
                'SELECT event_date, main_event FROM day_events WHERE trip_id = %s',
                (trip_id,)
            )
            main_events = {r['event_date']: r['main_event'] for r in cur.fetchall()}

            cur.execute(
                'SELECT id, event_date, time, end_time, text, note, transport FROM itinerary_items '
                'WHERE trip_id = %s ORDER BY event_date, sort_order, id',
                (trip_id,)
            )
            item_rows = cur.fetchall()

        items_by_date = {}
        for r in item_rows:
            items_by_date.setdefault(r['event_date'], []).append({
                'id': r['id'],
                'time': r['time'] or '',
                'endTime': r['end_time'] or '',
                'text': r['text'],
                'note': r['note'] or '',
                'transport': r['transport'],
            })

        days = []
        for d in date_range(trip['start_date'], trip['end_date']):
            days.append({
                'date': d,
                'mainEvent': main_events.get(d, ''),
                'items': items_by_date.get(d, []),
            })

        return jsonify({
            'id': trip['id'],
            'title': trip['title'],
            'startDate': trip['start_date'],
            'endDate': trip['end_date'],
            'checklist': checklist,
            'days': days,
        })
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


@app.route('/api/trips/<int:trip_id>', methods=['PUT'])
@login_required_api
def update_trip(trip_id):
    user_id = session['user_id']
    data = request.get_json(force=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not owns_trip(cur, trip_id, user_id):
                return jsonify({'error': 'not_found'}), 404
            cur.execute(
                'UPDATE trips SET title = COALESCE(%s, title), '
                'start_date = COALESCE(%s, start_date), '
                'end_date = COALESCE(%s, end_date), '
                'description = COALESCE(%s, description) WHERE id = %s',
                (data.get('title'), data.get('startDate'), data.get('endDate'),
                 data.get('description'), trip_id)
            )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


# ---------- checklist ----------

@app.route('/api/trips/<int:trip_id>/checklist', methods=['POST'])
@login_required_api
def add_checklist(trip_id):
    user_id = session['user_id']
    data = request.get_json(force=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'text_required'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not owns_trip(cur, trip_id, user_id):
                return jsonify({'error': 'not_found'}), 404
            cur.execute(
                'INSERT INTO checklist_items (trip_id, text, done) VALUES (%s, %s, false) '
                'RETURNING id, text, done',
                (trip_id, text)
            )
            row = cur.fetchone()
        conn.commit()
        return jsonify(row)
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


@app.route('/api/checklist/<int:item_id>', methods=['PATCH'])
@login_required_api
def update_checklist(item_id):
    user_id = session['user_id']
    data = request.get_json(force=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not owns_checklist_item(cur, item_id, user_id):
                return jsonify({'error': 'not_found'}), 404
            cur.execute(
                'UPDATE checklist_items SET done = COALESCE(%s, done), '
                'text = COALESCE(%s, text) WHERE id = %s',
                (data.get('done'), data.get('text'), item_id)
            )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


@app.route('/api/checklist/<int:item_id>', methods=['DELETE'])
@login_required_api
def delete_checklist(item_id):
    user_id = session['user_id']
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not owns_checklist_item(cur, item_id, user_id):
                return jsonify({'error': 'not_found'}), 404
            cur.execute('DELETE FROM checklist_items WHERE id = %s', (item_id,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


# ---------- day main event ----------

@app.route('/api/trips/<int:trip_id>/day', methods=['PUT'])
@login_required_api
def upsert_day(trip_id):
    user_id = session['user_id']
    data = request.get_json(force=True) or {}
    date_str = data.get('date')
    main_event = data.get('mainEvent', '')
    if not date_str:
        return jsonify({'error': 'date_required'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not owns_trip(cur, trip_id, user_id):
                return jsonify({'error': 'not_found'}), 404
            cur.execute(
                '''INSERT INTO day_events (trip_id, event_date, main_event)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (trip_id, event_date)
                   DO UPDATE SET main_event = EXCLUDED.main_event''',
                (trip_id, date_str, main_event)
            )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


# ---------- itinerary items ----------

@app.route('/api/trips/<int:trip_id>/items', methods=['POST'])
@login_required_api
def add_item(trip_id):
    user_id = session['user_id']
    data = request.get_json(force=True) or {}
    date_str = data.get('date')
    text = (data.get('text') or '').strip()
    note = (data.get('note') or '').strip()
    time_str = data.get('time') or ''
    end_time_str = data.get('endTime') or ''
    transport = bool(data.get('transport'))
    if not date_str or not text:
        return jsonify({'error': 'invalid'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not owns_trip(cur, trip_id, user_id):
                return jsonify({'error': 'not_found'}), 404
            cur.execute(
                'INSERT INTO itinerary_items (trip_id, event_date, time, end_time, text, note, transport) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s) '
                'RETURNING id, event_date, time, end_time AS "endTime", text, note, transport',
                (trip_id, date_str, time_str, end_time_str, text, note, transport)
            )
            row = cur.fetchone()
        conn.commit()
        return jsonify(row)
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


@app.route('/api/items/<int:item_id>', methods=['PATCH'])
@login_required_api
def update_item(item_id):
    user_id = session['user_id']
    data = request.get_json(force=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not owns_itinerary_item(cur, item_id, user_id):
                return jsonify({'error': 'not_found'}), 404
            cur.execute(
                'UPDATE itinerary_items SET time = COALESCE(%s, time), '
                'end_time = COALESCE(%s, end_time), '
                'text = COALESCE(%s, text), note = COALESCE(%s, note), '
                'transport = COALESCE(%s, transport) WHERE id = %s',
                (data.get('time'), data.get('endTime'), data.get('text'), data.get('note'),
                 data.get('transport'), item_id)
            )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


@app.route('/api/items/<int:item_id>', methods=['DELETE'])
@login_required_api
def delete_item(item_id):
    user_id = session['user_id']
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not owns_itinerary_item(cur, item_id, user_id):
                return jsonify({'error': 'not_found'}), 404
            cur.execute('DELETE FROM itinerary_items WHERE id = %s', (item_id,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.exception(e)
        conn.rollback()
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
