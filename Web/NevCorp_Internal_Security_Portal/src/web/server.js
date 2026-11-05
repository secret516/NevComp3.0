const express = require('express');
const cookieParser = require('cookie-parser');
const mysql = require('mysql2/promise');
const crypto = require('crypto');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const BOT_SECRET = process.env.BOT_SECRET || 'change_me';
const FLAG = process.env.FLAG || 'NevComp3.0{dummy_flag}';

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));
app.use(cookieParser());

const sessions = new Map();

function createSession(username, role) {
  const id = crypto.randomBytes(24).toString('hex');
  sessions.set(id, { username, role, createdAt: Date.now() });
  return id;
}

function getSession(req) {
  const id = req.cookies.session;
  if (!id) return null;
  return sessions.get(id) || null;
}

app.use((req, res, next) => {
  res.setHeader(
    'Content-Security-Policy',
    "default-src 'self'; " +
    "script-src 'self' 'unsafe-inline'; " +
    "object-src 'none'; " +
    "base-uri 'self'; " +
    "style-src 'self' 'unsafe-inline'; " +
    "img-src 'self' data: *; " +
    "connect-src 'self' *; " +
    "frame-ancestors 'none';"
  );
  next();
});

let pool;
async function initDb() {
  pool = await mysql.createPool({
    host: process.env.DB_HOST,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_NAME,
    waitForConnections: true,
    connectionLimit: 10,
  });
}

const SQLI_BANNED_WORDS = [
  'union', 'select', 'insert', 'update', 'delete', 'drop', 'create', 'alter',
  'exec', 'execute', 'information_schema', 'sleep', 'benchmark', 'load_file',
  'outfile', 'and', '--', '#', ';', 'xp_', 'having', 'group by', 'order by'
];

function isSqliBlocked(input) {
  if (typeof input !== 'string') return false;
  const lower = input.toLowerCase();
  return SQLI_BANNED_WORDS.some((w) => lower.includes(w));
}

const XSS_BANNED_PATTERNS = [
  /<iframe/i,
  /<object/i,
  /<embed/i,
  /<applet/i,
  /<script/i,              
  /document\s*\.\s*cookie/i, 
  /fetch\s*\(/i,                   
  /&#/i,
];

function isXssBlocked(input) {
  if (typeof input !== 'string') return false;
  return XSS_BANNED_PATTERNS.some((re) => re.test(input));
}

function requireStaff(req, res, next) {
  const sess = getSession(req);
  if (!sess || (sess.role !== 'staff' && sess.role !== 'superadmin')) {
    return res.redirect('/login');
  }
  req.session = sess;
  next();
}

function requireSuperadmin(req, res, next) {
  const sess = getSession(req);
  if (!sess || sess.role !== 'superadmin') {
    return res.status(403).render('error', {
      title: '403 Forbidden',
      message: 'Halaman ini cuma bisa diakses oleh SOC Lead (superadmin).',
    });
  }
  req.session = sess;
  next();
}

app.get('/', (req, res) => {
  const sess = getSession(req);
  res.render('index', { sess });
});

app.get('/login', (req, res) => {
  res.render('login', { error: null });
});

app.post('/login', async (req, res) => {
  const username = (req.body.username || '').toString();
  const password = (req.body.password || '').toString();

  if (isSqliBlocked(username) || isSqliBlocked(password)) {
    return res.render('login', {
      error: 'Blocked by WAF: pola berbahaya terdeteksi pada input.',
    });
  }

  const query = `SELECT * FROM users WHERE (username='${username}') AND (password='${password}')`;

  try {
    const [rows] = await pool.query(query);
    if (rows.length > 0) {
      const user = rows[0];
      const sessionId = createSession(user.username, user.role || 'staff');
      res.cookie('session', sessionId, { httpOnly: false, sameSite: 'Lax' });
      return res.redirect('/dashboard');
    }
    return res.render('login', { error: 'Username atau password salah.' });
  } catch (e) {
    return res.render('login', { error: 'Terjadi error pada query.' });
  }
});

app.get('/logout', (req, res) => {
  const id = req.cookies.session;
  if (id) sessions.delete(id);
  res.clearCookie('session');
  res.redirect('/login');
});

app.get('/dashboard', requireStaff, (req, res) => {
  res.render('dashboard', { session: req.session });
});

app.get('/reports', requireStaff, async (req, res) => {
  const [rows] = await pool.query(
    'SELECT * FROM reports WHERE author = ? ORDER BY id DESC',
    [req.session.username]
  );
  res.render('reports', { session: req.session, reports: rows, error: null });
});

app.get('/reports/new', requireStaff, (req, res) => {
  res.render('report_new', { session: req.session, error: null });
});

app.post('/reports/new', requireStaff, async (req, res) => {
  const title = (req.body.title || '').toString();
  const description = (req.body.description || '').toString();

  if (isXssBlocked(title) || isXssBlocked(description)) {
    return res.render('report_new', {
      session: req.session,
      error: 'Blocked by Security Filter: konten mengandung pola terlarang.',
    });
  }

  await pool.query(
    'INSERT INTO reports (author, title, description) VALUES (?, ?, ?)',
    [req.session.username, title, description]
  );

  res.redirect('/reports');
});


app.get('/admin/reports', requireSuperadmin, async (req, res) => {
  const [rows] = await pool.query('SELECT * FROM reports ORDER BY id DESC');
  res.render('admin_reports', { session: req.session, reports: rows });
});

app.get('/admin/flag', requireSuperadmin, (req, res) => {
  res.render('admin_flag', { session: req.session, flag: FLAG });
});

app.post('/internal/bot-session', (req, res) => {
  if (req.headers['x-bot-secret'] !== BOT_SECRET) {
    return res.status(403).json({ error: 'forbidden' });
  }
  const sessionId = createSession('soc_lead', 'superadmin');
  res.json({ sessionId });
});

initDb()
  .then(() => {
    app.listen(PORT, () => {
      console.log(`NevCorp SOC Portal running on port ${PORT}`);
    });
  })
  .catch((e) => {
    console.error('Failed to init DB', e);
    process.exit(1);
  });
