const puppeteer = require('puppeteer-core');

const WEB_URL = process.env.WEB_URL || 'http://web:3000';
const BOT_SECRET = process.env.BOT_SECRET || 'change_me';
const VISIT_INTERVAL_MS = parseInt(process.env.VISIT_INTERVAL_MS || '15000', 10);
const CHROMIUM_PATH = process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium';

function webHost(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return 'web';
  }
}

async function getSuperadminSessionId() {
  const res = await fetch(`${WEB_URL}/internal/bot-session`, {
    method: 'POST',
    headers: { 'X-Bot-Secret': BOT_SECRET },
  });
  if (!res.ok) throw new Error(`bot-session failed: ${res.status}`);
  const data = await res.json();
  return data.sessionId;
}

async function visitOnce() {
  let browser;
  try {
    const sessionId = await getSuperadminSessionId();

    browser = await puppeteer.launch({
      headless: 'new',
      executablePath: CHROMIUM_PATH,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    const page = await browser.newPage();

    await page.setCookie({
      name: 'session',
      value: sessionId,
      domain: webHost(WEB_URL),
      path: '/',
      httpOnly: false,
    });

    console.log(`[bot] Visiting ${WEB_URL}/admin/reports as SOC Lead...`);
    await page.goto(`${WEB_URL}/admin/reports`, {
      waitUntil: 'networkidle2',
      timeout: 20000,
    });

    await new Promise((r) => setTimeout(r, 4000));

    console.log('[bot] Review cycle done.');
  } catch (err) {
    console.error('[bot] Error during visit cycle:', err.message);
  } finally {
    if (browser) await browser.close();
  }
}

async function main() {
  console.log('[bot] SOC Lead review bot starting...');
  while (true) {
    await visitOnce();
    await new Promise((r) => setTimeout(r, VISIT_INTERVAL_MS));
  }
}

main();
