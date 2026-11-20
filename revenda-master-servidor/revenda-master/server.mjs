import { createServer } from 'node:http';
import { randomBytes, randomUUID, scrypt, timingSafeEqual } from 'node:crypto';
import { createReadStream, existsSync, mkdirSync, readFileSync, statSync } from 'node:fs';
import { copyFile, unlink, writeFile } from 'node:fs/promises';
import { basename, extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { DatabaseSync } from 'node:sqlite';

const root = fileURLToPath(new URL('.', import.meta.url));
const dataDir = resolve(process.env.DATA_DIR || resolve(root, 'data'));
const uploads = resolve(process.env.UPLOAD_DIR || resolve(dataDir, 'uploads'));
const frontend = resolve(root, 'frontend');
const seedDir = existsSync(resolve(root, 'backend/seed')) ? resolve(root, 'backend/seed') : resolve(root, 'seed');
const database = resolve(process.env.DATABASE_PATH || resolve(dataDir, 'catalog.sqlite3'));
const secure = process.env.NODE_ENV === 'production';
const maxUpload = 5 * 1024 * 1024;
const lifetime = 8 * 60 * 60;
const brands = ['Chevrolet', 'Volkswagen', 'Fiat', 'Jeep', 'Hyundai', 'Toyota', 'Honda', 'Renault'];
const transmissions = ['Manual', 'Automático'];
const fields = ['brand', 'model', 'version', 'year', 'year_label', 'color', 'transmission', 'description', 'sections', 'available'];
const derive = promisify(scrypt);
const sessions = new Map();
const attempts = new Map();

mkdirSync(dataDir, { recursive: true });
mkdirSync(uploads, { recursive: true });
const db = new DatabaseSync(database);
db.exec('PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;');
const existing = db.prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='vehicles'").get();
if (!existing) {
  db.exec('BEGIN');
  try {
    db.exec(readFileSync(resolve(root, 'schema.sql'), 'utf8'));
    const seed = JSON.parse(readFileSync(resolve(seedDir, 'vehicles.json'), 'utf8'));
    for (const vehicle of seed) {
      const id = insert(vehicle);
      for (const [position, name] of vehicle.photos.entries()) {
        const filename = randomUUID() + extname(name).toLowerCase();
        await copyFile(resolve(seedDir, 'images', name), resolve(uploads, filename));
        db.prepare('INSERT INTO photos (vehicle_id, filename, position) VALUES (?, ?, ?)').run(id, filename, position);
      }
    }
    db.exec('COMMIT');
  } catch (error) {
    db.exec('ROLLBACK');
    throw error;
  }
}

if (process.env.ADMIN_PASSWORD && !db.prepare('SELECT 1 FROM users LIMIT 1').get()) {
  const username = (process.env.ADMIN_USERNAME || 'admin').trim();
  const password = process.env.ADMIN_PASSWORD;
  if (!username || username.length > 64 || !validPassword(password)) {
    throw new Error('Configure usuário válido e senha inicial com 12 a 128 caracteres.');
  }
  db.prepare('INSERT INTO users (username, password_hash) VALUES (?, ?)').run(username, await passwordHash(password));
}

function validPassword(value) {
  return typeof value === 'string' && value.length >= 12 && value.length <= 128;
}

async function passwordHash(password) {
  const salt = randomBytes(16);
  const digest = await derive(password, salt, 32, { N: 16384, r: 8, p: 1 });
  return ['scrypt', 16384, 8, 1, salt.toString('base64'), digest.toString('base64')].join('$');
}

async function matchesPassword(password, hash) {
  const [, n, r, p, salt, digest] = hash.split('$');
  const expected = Buffer.from(digest, 'base64');
  const actual = await derive(password, Buffer.from(salt, 'base64'), expected.length, {
    N: Number(n), r: Number(r), p: Number(p), maxmem: 128 * 1024 * 1024
  });
  return timingSafeEqual(actual, expected);
}

const dummyHash = await passwordHash(randomBytes(32).toString('hex'));

function failure(status, message, fields) {
  return Object.assign(new Error(message), { status, fields });
}

function values(vehicle) {
  return fields.map(key => key === 'sections' ? JSON.stringify(vehicle.sections)
    : key === 'available' ? Number(vehicle.available) : vehicle[key]);
}

function insert(vehicle) {
  const params = fields.map(() => '?').join(', ');
  return db.prepare(`INSERT INTO vehicles (${fields.join(', ')}) VALUES (${params})`).run(...values(vehicle)).lastInsertRowid;
}

function validate(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw failure(400, 'Envie um objeto JSON.');
  const errors = {};
  const clean = (value, key, limit, required = false) => {
    if (value == null) value = '';
    if (typeof value !== 'string') {
      errors[key] = 'Precisa ser um texto.';
      return '';
    }
    value = value.replace(/[\x00-\x08\x0b-\x1f\x7f]/g, '').trim();
    if (value.length > limit || (required && !value)) errors[key] = `Informe um texto de até ${limit} caracteres.`;
    return value;
  };
  const vehicle = {
    brand: clean(input.brand, 'brand', 40, true),
    model: clean(input.model, 'model', 80, true),
    version: clean(input.version, 'version', 60),
    year: typeof input.year === 'string' && /^\d{4}$/.test(input.year.trim()) ? Number(input.year) : input.year,
    year_label: clean(input.year_label, 'year_label', 20),
    color: clean(input.color, 'color', 30),
    transmission: input.transmission,
    description: clean(input.description, 'description', 300),
    available: input.available === undefined ? true : input.available,
    sections: []
  };
  if (!brands.includes(vehicle.brand)) errors.brand = 'Fabricante inválido.';
  if (!Number.isInteger(vehicle.year) || vehicle.year < 1980 || vehicle.year > 2100) errors.year = 'Informe um ano entre 1980 e 2100.';
  if (!transmissions.includes(vehicle.transmission)) errors.transmission = 'Escolha Manual ou Automático.';
  if (typeof vehicle.available !== 'boolean') errors.available = 'Informe a disponibilidade.';
  const sections = input.sections ?? [];
  if (!Array.isArray(sections) || sections.length > 10) {
    errors.sections = 'Use no máximo 10 blocos de detalhes.';
  } else {
    for (const section of sections) {
      if (!section || !Array.isArray(section.items ?? []) || (section.items ?? []).length > 20) {
        errors.sections = 'Cada bloco deve ter um título e até 20 itens.';
        break;
      }
      vehicle.sections.push({
        title: clean(section.title, 'sections', 60, true),
        items: (section.items ?? []).map(item => clean(item, 'sections', 200)).filter(Boolean)
      });
    }
  }
  if (Object.keys(errors).length) throw failure(400, 'Confira os dados do veículo.', errors);
  return vehicle;
}

const listing = db.prepare(`SELECT v.*, (SELECT filename FROM photos WHERE vehicle_id=v.id ORDER BY position, id LIMIT 1) AS first_photo
  FROM vehicles v ORDER BY brand COLLATE NOCASE, model COLLATE NOCASE, year DESC, id`);
const photosFor = db.prepare('SELECT * FROM photos WHERE vehicle_id=? ORDER BY position, id');
const vehicleFor = db.prepare('SELECT * FROM vehicles WHERE id=?');
const uploadUrl = name => '/uploads/' + encodeURIComponent(name);

function vehicleOrFail(id) {
  const vehicle = vehicleFor.get(id);
  if (!vehicle) throw failure(404, 'Veículo não encontrado.');
  return vehicle;
}

function card(row, photo) {
  const result = Object.fromEntries(['id', ...fields.filter(key => key !== 'sections')].map(key => [key, row[key]]));
  return { ...result, available: Boolean(row.available), photo: photo ? uploadUrl(photo) : null };
}

function detail(id) {
  const row = vehicleOrFail(id);
  const photos = photosFor.all(id);
  return {
    ...card(row, photos[0]?.filename),
    sections: JSON.parse(row.sections),
    photos: photos.map(({ id, filename }) => ({ id, url: uploadUrl(filename) }))
  };
}

function metadata() {
  const rows = listing.all();
  const models = Object.fromEntries(brands.map(brand => [brand, []]));
  for (const { brand, model } of rows) {
    const group = models[brand] ??= [];
    if (!group.includes(model)) group.push(model);
  }
  return {
    brands, transmissions, models_by_brand: models,
    colors: [...new Set(rows.map(row => row.color).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR')),
    years: [...new Set(rows.map(row => row.year))].sort((a, b) => b - a),
    whatsapp: (process.env.WHATSAPP_NUMBER || '').replace(/\D/g, ''),
    address: process.env.STORE_ADDRESS || 'Av. Imperial, 1200, Centro'
  };
}

function search(params) {
  const filters = ['brand', 'model', 'year', 'color', 'transmission', 'q'].map(key => [key, (params.get(key) || '').trim()]);
  if (filters.some(([key, value]) => value.length > 80 || (key === 'year' && value && !/^\d{1,4}$/.test(value)))) {
    throw failure(400, 'Filtro inválido.');
  }
  const lower = value => String(value).toLocaleLowerCase('pt-BR');
  const items = listing.all().filter(row => filters.every(([key, value]) => {
    if (!value) return true;
    if (key === 'q') return [row.brand, row.model, row.version, row.description].some(field => lower(field).includes(lower(value)));
    if (key === 'year') return row.year === Number(value);
    return lower(row[key]) === lower(value);
  })).map(row => card(row, row.first_photo));
  return { items, count: items.length };
}

async function readBody(req, limit) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req.iterator({ destroyOnReturn: false })) {
    size += chunk.length;
    if (size > limit) {
      req.resume();
      throw failure(413, 'Arquivo ou solicitação acima do limite.');
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks, size);
}

async function jsonBody(req) {
  if (!/^application\/json(?:\s*;|$)/i.test(req.headers['content-type'] || '')) throw failure(415, 'Envie um objeto JSON.');
  const body = await readBody(req, 64 * 1024);
  try {
    const data = JSON.parse(body);
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error();
    return data;
  } catch {
    throw failure(400, 'Envie um objeto JSON válido.');
  }
}

function prune(map) {
  const now = Date.now();
  for (const [key, entry] of map) if (entry.expires <= now) map.delete(key);
}

setInterval(() => {
  prune(sessions);
  prune(attempts);
}, 60_000).unref();

function session(req) {
  const token = req.headers.cookie?.match(/(?:^|;\s*)revenda_session=([a-f0-9]{64})(?:;|$)/)?.[1];
  const entry = sessions.get(token);
  if (!entry || entry.expires <= Date.now()) return null;
  return { ...entry, token };
}

function cookie(res, token, maxAge) {
  res.setHeader('Set-Cookie', `revenda_session=${token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${maxAge}${secure ? '; Secure' : ''}`);
}

function startSession(req, res, user) {
  const previous = session(req);
  if (previous) sessions.delete(previous.token);
  if (sessions.size >= 10_000) sessions.delete(sessions.keys().next().value);
  const token = randomBytes(32).toString('hex');
  const csrf = randomBytes(32).toString('hex');
  sessions.set(token, { id: user.id, username: user.username, csrf, expires: Date.now() + lifetime * 1000 });
  cookie(res, token, lifetime);
  return { authenticated: true, username: user.username, csrf_token: csrf };
}

async function login(req, res) {
  const { username, password } = await jsonBody(req);
  if (typeof username !== 'string' || !username.trim() || username.length > 64
      || typeof password !== 'string' || !password || password.length > 128) throw failure(400, 'Informe usuário e senha.');
  const loginName = username.trim().toLowerCase();
  const user = db.prepare('SELECT * FROM users WHERE username = ? COLLATE NOCASE').get(loginName);
  const keys = ['ip:' + req.socket.remoteAddress, ...(user ? ['user:' + user.id] : [])];
  for (const key of keys) {
    const record = attempts.get(key);
    if (record && record.expires > Date.now() && record.count >= 8) throw failure(429, 'Muitas tentativas. Tente novamente mais tarde.');
  }
  for (const key of keys) {
    const record = attempts.get(key);
    if (record && record.expires > Date.now()) record.count++;
    else attempts.set(key, { count: 1, expires: Date.now() + 900_000 });
  }
  const matched = await matchesPassword(password, user?.password_hash ?? dummyHash);
  if (!user || !matched) throw failure(401, 'Usuário ou senha incorretos.');
  for (const key of keys) attempts.delete(key);
  return startSession(req, res, user);
}

function invalidate(userId) {
  for (const [token, entry] of sessions) if (entry.id === userId) sessions.delete(token);
}

function adminSession(req) {
  const current = session(req);
  if (!current) throw failure(401, 'Entre para continuar.');
  if (req.headers['x-csrf-token'] !== current.csrf) throw failure(403, 'Sessão inválida. Entre novamente.');
  return current;
}

function imageExtension(bytes) {
  if (bytes.length < 16) return null;
  if (bytes.subarray(0, 3).equals(Buffer.from([255, 216, 255])) && bytes.subarray(-2).equals(Buffer.from([255, 217]))) return '.jpg';
  if (bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) && bytes.toString('ascii', 12, 16) === 'IHDR') return '.png';
  if (bytes.toString('ascii', 0, 4) === 'RIFF' && bytes.toString('ascii', 8, 12) === 'WEBP' && bytes.readUInt32LE(4) === bytes.length - 8) return '.webp';
  return null;
}

async function addPhoto(req, id) {
  vehicleOrFail(id);
  const type = req.headers['content-type'] || '';
  if (!/^multipart\/form-data;/i.test(type)) throw failure(400, 'Selecione uma foto.');
  const body = await readBody(req, maxUpload + 64 * 1024);
  let photo;
  try {
    const multipart = new Response(body, { headers: { 'content-type': type } });
    photo = (await multipart.formData()).get('photo');
  } catch {
    throw failure(400, 'Envio de foto inválido.');
  }
  if (!(photo instanceof File) || photo.size > maxUpload) throw failure(400, 'Selecione uma foto de até 5 MB.');
  const bytes = Buffer.from(await photo.arrayBuffer());
  const ext = imageExtension(bytes);
  if (!ext) throw failure(400, 'Selecione uma imagem JPG, PNG ou WebP.');
  const filename = randomUUID() + ext;
  await writeFile(resolve(uploads, filename), bytes, { flag: 'wx' });
  try {
    const photos = photosFor.all(id);
    if (photos.length >= 12) throw failure(409, 'Cada veículo aceita até 12 fotos.');
    const position = (photos.at(-1)?.position ?? -1) + 1;
    db.prepare('INSERT INTO photos (vehicle_id, filename, position) VALUES (?, ?, ?)').run(id, filename, position);
  } catch (error) {
    await removeUpload(filename);
    throw error;
  }
  return detail(id);
}

async function removeUpload(name) {
  if (basename(name) !== name) return;
  await unlink(resolve(uploads, name)).catch(error => {
    if (error.code !== 'ENOENT') console.error('Falha ao remover uma foto do armazenamento.');
  });
}

const mime = new Map([
  ['.html', 'text/html; charset=utf-8'], ['.js', 'text/javascript; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'], ['.jpg', 'image/jpeg'], ['.jpeg', 'image/jpeg'],
  ['.png', 'image/png'], ['.webp', 'image/webp'], ['.mp4', 'video/mp4'], ['.ico', 'image/x-icon']
]);

function serveFile(req, res, directory, name) {
  const file = resolve(directory, name);
  const type = mime.get(extname(file).toLowerCase());
  if (!type || !file.startsWith(directory + sep)) throw failure(404, 'Arquivo não encontrado.');
  const info = statSync(file, { throwIfNoEntry: false });
  if (!info?.isFile()) throw failure(404, 'Arquivo não encontrado.');
  res.setHeader('Content-Type', type);
  res.setHeader('Cache-Control', type.startsWith('text/html') ? 'no-cache' : 'public, max-age=3600');
  let start = 0;
  let end = info.size - 1;
  if (type === 'video/mp4') {
    res.setHeader('Accept-Ranges', 'bytes');
    const range = req.headers.range?.match(/^bytes=(\d*)-(\d*)$/);
    if (range && (range[1] || range[2])) {
      start = range[1] ? Number(range[1]) : Math.max(0, info.size - Number(range[2]));
      end = range[1] && range[2] ? Math.min(end, Number(range[2])) : end;
      if (start > end) {
        res.writeHead(416, { 'Content-Range': `bytes */${info.size}` }).end();
        return;
      }
      res.statusCode = 206;
      res.setHeader('Content-Range', `bytes ${start}-${end}/${info.size}`);
    }
  }
  res.setHeader('Content-Length', end - start + 1);
  if (req.method === 'HEAD' || info.size === 0) return res.end();
  const stream = createReadStream(file, { start, end });
  stream.on('error', () => res.destroy());
  res.on('close', () => stream.destroy());
  stream.pipe(res);
}

function json(res, data, status = 200) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(data));
}

const pages = new Map([['/', 'index.html'], ['/veiculo', 'veiculo.html'], ['/admin', 'admin.html']]);
const mutations = new Set(['POST', 'PUT', 'DELETE']);

async function route(req, res) {
  const url = new URL(req.url, 'http://localhost');
  const path = decodeURIComponent(url.pathname);
  const method = req.method;
  if (mutations.has(method) && req.headers['sec-fetch-site'] === 'cross-site') throw failure(403, 'Origem inválida.');
  if (method === 'GET' || method === 'HEAD') {
    if (pages.has(path)) return serveFile(req, res, frontend, pages.get(path));
    if (path.startsWith('/assets/')) return serveFile(req, res, resolve(frontend, 'assets'), path.slice(8));
    if (path.startsWith('/uploads/') && /^[\w.-]+$/.test(path.slice(9))) return serveFile(req, res, uploads, path.slice(9));
  }
  if (method === 'GET') {
    if (path === '/api/health') return json(res, { status: 'ok' });
    if (path === '/api/meta') return json(res, metadata());
    if (path === '/api/vehicles') return json(res, search(url.searchParams));
    const vehicle = path.match(/^\/api\/vehicles\/(\d+)$/);
    if (vehicle) return json(res, detail(Number(vehicle[1])));
    if (path === '/api/auth/me') {
      const current = session(req);
      return json(res, current ? { authenticated: true, username: current.username, csrf_token: current.csrf } : { authenticated: false });
    }
  }
  if (method === 'POST' && path === '/api/auth/login') return json(res, await login(req, res));
  if (method === 'POST' && path === '/api/auth/logout') {
    invalidate(adminSession(req).id);
    cookie(res, '', 0);
    return json(res, { ok: true });
  }
  if (method === 'POST' && path === '/api/auth/password') {
    const current = adminSession(req);
    const input = await jsonBody(req);
    const user = db.prepare('SELECT * FROM users WHERE id=?').get(current.id);
    if (typeof input.current !== 'string' || input.current.length > 128 || !validPassword(input.new)) {
      throw failure(400, 'Informe a senha atual e uma nova senha de 12 a 128 caracteres.');
    }
    if (!await matchesPassword(input.current, user.password_hash)) throw failure(400, 'Senha atual incorreta.');
    const hash = await passwordHash(input.new);
    const result = db.prepare('UPDATE users SET password_hash=?, session_version=session_version+1 WHERE id=? AND password_hash=?')
      .run(hash, user.id, user.password_hash);
    if (!result.changes) throw failure(409, 'A senha foi alterada. Entre novamente.');
    invalidate(user.id);
    return json(res, { ok: true, csrf_token: startSession(req, res, user).csrf_token });
  }
  if (path.startsWith('/api/admin/') && mutations.has(method)) {
    adminSession(req);
    if (method === 'POST' && path === '/api/admin/vehicles') return json(res, detail(insert(validate(await jsonBody(req)))), 201);
    const vehicle = path.match(/^\/api\/admin\/vehicles\/(\d+)(\/photos)?$/);
    if (vehicle) {
      const id = Number(vehicle[1]);
      if (vehicle[2] && method === 'POST') return json(res, await addPhoto(req, id), 201);
      if (!vehicle[2] && method === 'PUT') {
        const input = validate(await jsonBody(req));
        vehicleOrFail(id);
        db.prepare(`UPDATE vehicles SET ${fields.map(key => key + '=?').join(', ')}, updated_at=datetime('now') WHERE id=?`).run(...values(input), id);
        return json(res, detail(id));
      }
      if (!vehicle[2] && method === 'DELETE') {
        vehicleOrFail(id);
        const photos = photosFor.all(id);
        db.prepare('DELETE FROM vehicles WHERE id=?').run(id);
        await Promise.all(photos.map(photo => removeUpload(photo.filename)));
        res.writeHead(204).end();
        return;
      }
    }
    const photoRoute = path.match(/^\/api\/admin\/photos\/(\d+)(\/main)?$/);
    if (photoRoute) {
      const photo = db.prepare('SELECT * FROM photos WHERE id=?').get(Number(photoRoute[1]));
      if (!photo) throw failure(404, 'Foto não encontrada.');
      if (photoRoute[2] && method === 'POST') {
        db.prepare('UPDATE photos SET position=(SELECT MIN(position)-1 FROM photos WHERE vehicle_id=?) WHERE id=?').run(photo.vehicle_id, photo.id);
        return json(res, detail(photo.vehicle_id));
      }
      if (!photoRoute[2] && method === 'DELETE') {
        db.prepare('DELETE FROM photos WHERE id=?').run(photo.id);
        const result = detail(photo.vehicle_id);
        await removeUpload(photo.filename);
        return json(res, result);
      }
    }
  }
  throw failure(404, 'Página não encontrada.');
}

const server = createServer(async (req, res) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('X-Frame-Options', 'DENY');
  try {
    await route(req, res);
  } catch (error) {
    if (res.headersSent) return res.destroy();
    const status = error.status || (error instanceof URIError ? 400 : 500);
    if (status === 500) console.error(error.message);
    json(res, { error: { message: status === 500 ? 'Erro interno.' : error.message, fields: error.fields } }, status);
  }
});
server.listen(Number(process.env.PORT || 4173), process.env.HOST || '0.0.0.0');
