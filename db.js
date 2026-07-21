const { Pool } = require('pg');

if (!process.env.DATABASE_URL) {
  console.warn('경고: DATABASE_URL 환경변수가 설정되어 있지 않아요. Render에서 PostgreSQL을 연결하고 환경변수를 등록해주세요.');
}

const isProd = process.env.NODE_ENV === 'production';

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: isProd ? { rejectUnauthorized: false } : false
});

module.exports = pool;
