const express = require('express');
const path = require('path');
const fs = require('fs');
const pool = require('./db');

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const PORT = process.env.PORT || 3000;

// ---------- helpers ----------

function dateRange(startStr, endStr) {
  const dates = [];
  let cur = new Date(startStr + 'T00:00:00Z');
  const last = new Date(endStr + 'T00:00:00Z');
  if (isNaN(cur) || isNaN(last) || cur > last) return [startStr];
  while (cur <= last) {
    dates.push(cur.toISOString().slice(0, 10));
    cur.setUTCDate(cur.getUTCDate() + 1);
  }
  return dates;
}

async function getTripId() {
  const { rows } = await pool.query('SELECT id FROM trips ORDER BY id LIMIT 1');
  return rows[0].id;
}

async function initDb() {
  const schema = fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf8');
  await pool.query(schema);
  const { rows } = await pool.query('SELECT id FROM trips ORDER BY id LIMIT 1');
  if (rows.length === 0) {
    await pool.query(
      'INSERT INTO trips (title, start_date, end_date) VALUES ($1, $2, $3)',
      ['나의 여행', '2026-10-07', '2026-10-10']
    );
  }
}

// ---------- trip ----------

app.get('/api/trip', async (req, res) => {
  try {
    const tripId = await getTripId();
    const tripRes = await pool.query('SELECT * FROM trips WHERE id = $1', [tripId]);
    const trip = tripRes.rows[0];

    const checklistRes = await pool.query(
      'SELECT id, text, done FROM checklist_items WHERE trip_id = $1 ORDER BY sort_order, id',
      [tripId]
    );
    const dayEventsRes = await pool.query(
      'SELECT event_date, main_event FROM day_events WHERE trip_id = $1',
      [tripId]
    );
    const itemsRes = await pool.query(
      'SELECT id, event_date, time, text, transport FROM itinerary_items WHERE trip_id = $1 ORDER BY event_date, sort_order, id',
      [tripId]
    );

    const mainEventByDate = {};
    dayEventsRes.rows.forEach(r => { mainEventByDate[r.event_date] = r.main_event; });

    const itemsByDate = {};
    itemsRes.rows.forEach(r => {
      if (!itemsByDate[r.event_date]) itemsByDate[r.event_date] = [];
      itemsByDate[r.event_date].push({
        id: r.id, time: r.time || '', text: r.text, transport: r.transport
      });
    });

    const days = dateRange(trip.start_date, trip.end_date).map(date => ({
      date,
      mainEvent: mainEventByDate[date] || '',
      items: itemsByDate[date] || []
    }));

    res.json({
      id: trip.id,
      title: trip.title,
      startDate: trip.start_date,
      endDate: trip.end_date,
      checklist: checklistRes.rows,
      days
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'server_error' });
  }
});

app.put('/api/trip', async (req, res) => {
  try {
    const tripId = await getTripId();
    const { title, startDate, endDate } = req.body;
    await pool.query(
      'UPDATE trips SET title = COALESCE($1, title), start_date = COALESCE($2, start_date), end_date = COALESCE($3, end_date) WHERE id = $4',
      [title, startDate, endDate, tripId]
    );
    res.json({ ok: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'server_error' });
  }
});

// ---------- checklist ----------

app.post('/api/checklist', async (req, res) => {
  try {
    const tripId = await getTripId();
    const text = (req.body.text || '').trim();
    if (!text) return res.status(400).json({ error: 'text_required' });
    const { rows } = await pool.query(
      'INSERT INTO checklist_items (trip_id, text, done) VALUES ($1, $2, false) RETURNING id, text, done',
      [tripId, text]
    );
    res.json(rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'server_error' });
  }
});

app.patch('/api/checklist/:id', async (req, res) => {
  try {
    const { done, text } = req.body;
    await pool.query(
      'UPDATE checklist_items SET done = COALESCE($1, done), text = COALESCE($2, text) WHERE id = $3',
      [done, text, req.params.id]
    );
    res.json({ ok: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'server_error' });
  }
});

app.delete('/api/checklist/:id', async (req, res) => {
  try {
    await pool.query('DELETE FROM checklist_items WHERE id = $1', [req.params.id]);
    res.json({ ok: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'server_error' });
  }
});

// ---------- day main event ----------

app.put('/api/day', async (req, res) => {
  try {
    const tripId = await getTripId();
    const { date, mainEvent } = req.body;
    if (!date) return res.status(400).json({ error: 'date_required' });
    await pool.query(
      `INSERT INTO day_events (trip_id, event_date, main_event)
       VALUES ($1, $2, $3)
       ON CONFLICT (trip_id, event_date)
       DO UPDATE SET main_event = EXCLUDED.main_event`,
      [tripId, date, mainEvent || '']
    );
    res.json({ ok: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'server_error' });
  }
});

// ---------- itinerary items ----------

app.post('/api/items', async (req, res) => {
  try {
    const tripId = await getTripId();
    const { date, time, transport } = req.body;
    const text = (req.body.text || '').trim();
    if (!date || !text) return res.status(400).json({ error: 'invalid' });
    const { rows } = await pool.query(
      'INSERT INTO itinerary_items (trip_id, event_date, time, text, transport) VALUES ($1,$2,$3,$4,$5) RETURNING id, event_date, time, text, transport',
      [tripId, date, time || '', text, !!transport]
    );
    res.json(rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'server_error' });
  }
});

app.patch('/api/items/:id', async (req, res) => {
  try {
    const { time, text, transport } = req.body;
    await pool.query(
      'UPDATE itinerary_items SET time = COALESCE($1, time), text = COALESCE($2, text), transport = COALESCE($3, transport) WHERE id = $4',
      [time, text, transport, req.params.id]
    );
    res.json({ ok: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'server_error' });
  }
});

app.delete('/api/items/:id', async (req, res) => {
  try {
    await pool.query('DELETE FROM itinerary_items WHERE id = $1', [req.params.id]);
    res.json({ ok: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'server_error' });
  }
});

initDb()
  .then(() => {
    app.listen(PORT, () => console.log(`Trip planner listening on port ${PORT}`));
  })
  .catch(err => {
    console.error('DB 초기화 실패:', err);
    process.exit(1);
  });
