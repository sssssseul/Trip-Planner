import os
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_from_directory, redirect
import psycopg2
import psycopg2.extras

app = Flask(__name__)

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
            cur.execute('SELECT id FROM trips ORDER BY id LIMIT 1')
            row = cur.fetchone()
            if not row:
                cur.execute(
                    'INSERT INTO trips (title, start_date, end_date) VALUES (%s, %s, %s)',
                    ('나의 여행', '2026-10-07', '2026-10-10')
                )
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


# ---------- 화면 ----------

@app.route('/')
def root():
    return redirect('/trips')


@app.route('/trips')
def trips_page():
    return send_from_directory(BASE_DIR, 'trips.html')


@app.route('/trips.js')
def trips_js():
    return send_from_directory(BASE_DIR, 'trips.js')


@app.route('/trip/<int:trip_id>')
def trip_page(trip_id):
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/app.js')
def app_js():
    return send_from_directory(BASE_DIR, 'app.js')


# ---------- app settings ----------

@app.route('/api/settings', methods=['GET'])
def get_settings():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT trips_title FROM app_settings ORDER BY id LIMIT 1')
            row = cur.fetchone()
        return jsonify({'tripsTitle': row['trips_title'] if row else '내 여행들'})
    except Exception as e:
        app.logger.exception(e)
        return jsonify({'error': 'server_error'}), 500
    finally:
        conn.close()


@app.route('/api/settings', methods=['PUT'])
def update_settings():
    data = request.get_json(force=True) or {}
    trips_title = (data.get('tripsTitle') or '').strip()
    if not trips_title:
        return jsonify({'error': 'title_required'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM app_settings ORDER BY id LIMIT 1')
            row = cur.fetchone()
            if row:
                cur.execute(
                    'UPDATE app_settings SET trips_title = %s WHERE id = %s',
                    (trips_title, row['id'])
                )
            else:
                cur.execute(
                    'INSERT INTO app_settings (trips_title) VALUES (%s)', (trips_title,)
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
def list_trips():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id, title, start_date, end_date, description FROM trips ORDER BY id ASC'
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
def create_trip():
    data = request.get_json(force=True) or {}
    title = (data.get('title') or '').strip() or '새 여행'
    today = datetime.now().date().isoformat()
    start_date = data.get('startDate') or today
    end_date = data.get('endDate') or start_date
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO trips (title, start_date, end_date) VALUES (%s, %s, %s) '
                'RETURNING id',
                (title, start_date, end_date)
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
def delete_trip(trip_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
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
def get_trip(trip_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM trips WHERE id = %s', (trip_id,))
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
def update_trip(trip_id):
    data = request.get_json(force=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
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
def add_checklist(trip_id):
    data = request.get_json(force=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'text_required'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
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
def update_checklist(item_id):
    data = request.get_json(force=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
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
def delete_checklist(item_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
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
def upsert_day(trip_id):
    data = request.get_json(force=True) or {}
    date_str = data.get('date')
    main_event = data.get('mainEvent', '')
    if not date_str:
        return jsonify({'error': 'date_required'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
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
def add_item(trip_id):
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
def update_item(item_id):
    data = request.get_json(force=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
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
def delete_item(item_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
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
