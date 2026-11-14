import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json",
};

const json = (status: number, body: Record<string, unknown>) =>
  new Response(JSON.stringify(body), { status, headers: cors });

function publicUser(user: any) {\n  if (!user || typeof user !== "object") return user;\n  const { password_hash: _passwordHash, ...safe } = user;\n  return safe;\n}\n\nasync function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest)).map(x => x.toString(16).padStart(2, "0")).join("");
}

async function verifyInitData(initData: string, botToken: string) {
  if (!initData || initData.length > 8192) throw new Error("Откройте Mini App через Telegram.");
  const params = new URLSearchParams(initData);
  const receivedHash = params.get("hash");
  const authDate = Number(params.get("auth_date") || 0);
  if (!receivedHash || !authDate || Math.abs(Date.now() / 1000 - authDate) > 600) {
    throw new Error("Сессия Telegram устарела. Закройте и снова откройте Mini App.");
  }
  params.delete("hash");
  const check = Array.from(params.entries()).sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`).join("\n");
  const enc = new TextEncoder();
  const secretKey = await crypto.subtle.importKey("raw", enc.encode(botToken), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const secret = await crypto.subtle.sign("HMAC", secretKey, enc.encode("WebAppData"));
  const dataKey = await crypto.subtle.importKey("raw", secret, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const expected = Array.from(new Uint8Array(await crypto.subtle.sign("HMAC", dataKey, enc.encode(check))))
    .map(x => x.toString(16).padStart(2, "0")).join("");
  const a = new TextEncoder().encode(expected), b = new TextEncoder().encode(receivedHash);
  if (a.length !== b.length) throw new Error("Не удалось подтвердить аккаунт Telegram.");
  let diff = 0; for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  if (diff !== 0) throw new Error("Не удалось подтвердить аккаунт Telegram.");
  const rawUser = params.get("user");
  if (!rawUser) throw new Error("В Telegram-профиле не найден пользователь.");
  const user = JSON.parse(rawUser);
  if (!user?.id || !Number.isSafeInteger(Number(user.id))) throw new Error("Некорректный Telegram ID.");
  return { id: Number(user.id), username: String(user.username || "") };
}

async function rest(path: string, key: string, init: RequestInit = {}) {
  const base = Deno.env.get("SUPABASE_URL")!;
  const response = await fetch(`${base}/rest/v1/${path}`, {
    ...init,
    headers: {
      apikey: key, Authorization: `Bearer ${key}`,
      "Content-Type": "application/json", Prefer: "return=representation",
      ...(init.headers || {}),
    },
  });
  const text = await response.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!response.ok) throw new Error(typeof data === "string" ? data : (data?.message || data?.hint || "Ошибка базы данных"));
  return data;
}

async function telegramSend(botToken: string, chatId: number, code: string) {
  const r = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text: `🔐 Код подтверждения ARZstore: ${code}\n\nКод действует 5 минут. Никому его не сообщайте.`,
    }),
  });
  const d = await r.json();
  if (!r.ok || !d.ok) {
    if (d?.error_code === 403) throw new Error("Сначала откройте бота @arizona_coin_bot и нажмите /start, затем запросите код ещё раз.");
    throw new Error("Telegram не смог доставить код. Откройте бота и попробуйте снова.");
  }
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json(405, { ok: false, error: "Метод не поддерживается." });

  try {
    const botToken = Deno.env.get("BOT_TOKEN");
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!botToken || !serviceKey) return json(503, { ok: false, error: "Сервер регистрации ещё не настроен: добавьте BOT_TOKEN в секреты Supabase Functions." });

    const body = await req.json();
    const tg = await verifyInitData(String(body.initData || ""), botToken);
    const now = Date.now();
    const table = "arzstore_registration_challenges";
    const existingRows = await rest(`${table}?telegram_id=eq.${tg.id}&select=*`, serviceKey);
    const old = Array.isArray(existingRows) ? existingRows[0] : null;

    if (body.action === "login") {
      const username = String(body.username || "").trim().toLowerCase();
      const passwordHash = String(body.password_hash || "");
      if (!/^[a-zA-Z0-9_]{3,20}$/.test(username) || !/^[a-f0-9]{64}$/i.test(passwordHash)) {
        return json(400, { ok: false, error: "Проверьте логин и пароль." });
      }
      const found = await rest(`app_users?username=eq.${encodeURIComponent(username)}&select=*&limit=1`, serviceKey);
      const user = Array.isArray(found) ? found[0] : null;
      if (!user || !user.password_hash || user.password_hash !== passwordHash) {
        return json(401, { ok: false, error: "Неверный логин или пароль." });
      }
      if (user.banned) return json(403, { ok: false, error: "Аккаунт заблокирован." });
      if (user.telegram_id && Number(user.telegram_id) !== tg.id) {
        return json(409, { ok: false, error: "Этот аккаунт уже привязан к другому Telegram." });
      }
      const linked = await rest(`app_users?telegram_id=eq.${tg.id}&select=id&limit=2`, serviceKey);
      if (Array.isArray(linked) && linked.some((row: any) => row.id !== user.id)) {
        return json(409, { ok: false, error: "К этому Telegram уже привязан другой аккаунт." });
      }
      const updated = await rest(`app_users?id=eq.${user.id}`, serviceKey, {
        method: "PATCH",
        body: JSON.stringify({ telegram_id: tg.id, last_seen_at: new Date().toISOString() }),
      });
      const safeUser = publicUser(Array.isArray(updated) ? updated[0] : user);
      return json(200, { ok: true, user: safeUser });
    }

    if (body.action === "session") {
      const userId = String(body.user_id || "");
      if (!/^[0-9a-f-]{36}$/i.test(userId)) return json(400, { ok: false, error: "Некорректная сессия." });
      const found = await rest(`app_users?id=eq.${encodeURIComponent(userId)}&telegram_id=eq.${tg.id}&select=*&limit=1`, serviceKey);
      const user = Array.isArray(found) ? found[0] : null;
      if (!user) return json(401, { ok: false, error: "Сессия не найдена. Войдите снова." });
      if (user.banned) return json(403, { ok: false, error: "Аккаунт заблокирован." });
      const updated = await rest(`app_users?id=eq.${user.id}`, serviceKey, {
        method: "PATCH",
        body: JSON.stringify({ last_seen_at: new Date().toISOString() }),
      });
      return json(200, { ok: true, user: publicUser(Array.isArray(updated) ? updated[0] : user) });
    }

    if (body.action === "request") {
      const username = String(body.username || "").trim().toLowerCase();
      const passwordHash = String(body.password_hash || "");
      if (!/^[a-zA-Z0-9_]{3,20}$/.test(username)) return json(400, { ok: false, error: "Логин должен содержать 3–20 латинских букв, цифр или _." });
      if (!/^[a-f0-9]{64}$/i.test(passwordHash)) return json(400, { ok: false, error: "Не удалось обработать пароль. Повторите попытку." });

      const matches = await rest(`app_users?username=ilike.${encodeURIComponent(username)}&select=id,telegram_id&limit=2`, serviceKey);
      if (Array.isArray(matches) && matches.some((x: any) => Number(x.telegram_id) !== tg.id)) {
        return json(409, { ok: false, error: "Этот логин уже занят." });
      }

      const windowStart = old?.window_started_at ? new Date(old.window_started_at).getTime() : 0;
      const windowActive = windowStart && now - windowStart < 7 * 60 * 60 * 1000;
      if (old?.blocked_until && new Date(old.blocked_until).getTime() > now) {
        return json(429, { ok: false, error: "Лимит кодов исчерпан. Попробуйте через 7 часов." });
      }
      if (windowActive && Number(old.sent_count || 0) >= 3) {
        return json(429, { ok: false, error: "Вы запросили 3 кода. Следующая отправка будет доступна через 7 часов." });
      }
      if (old?.last_sent_at && now - new Date(old.last_sent_at).getTime() < 5 * 60 * 1000) {
        const seconds = Math.ceil((5 * 60 * 1000 - (now - new Date(old.last_sent_at).getTime())) / 1000);
        return json(429, { ok: false, error: `Повторная отправка будет доступна через ${Math.ceil(seconds / 60)} мин.` });
      }

      const code = String(crypto.getRandomValues(new Uint32Array(1))[0] % 1000000).padStart(6, "0");
      const newWindowStart = windowActive ? old.window_started_at : new Date(now).toISOString();
      const sentCount = windowActive ? Number(old.sent_count || 0) + 1 : 1;
      const challenge = {
        telegram_id: tg.id, username, password_hash: passwordHash,
        code_hash: await sha256(code), expires_at: new Date(now + 5 * 60 * 1000).toISOString(),
        sent_count: sentCount, window_started_at: newWindowStart,
        last_sent_at: new Date(now).toISOString(),
        blocked_until: sentCount >= 3 ? new Date(now + 7 * 60 * 60 * 1000).toISOString() : null,
        attempts: 0,
      };
      await rest(`${table}?on_conflict=telegram_id`, serviceKey, {
        method: "POST", headers: { Prefer: "resolution=merge-duplicates,return=representation" },
        body: JSON.stringify(challenge),
      });
      try {
        await telegramSend(botToken, tg.id, code);
      } catch (e) {
        await rest(`${table}?telegram_id=eq.${tg.id}`, serviceKey, { method: "DELETE" }).catch(() => null);
        throw e;
      }
      return json(200, { ok: true, message: "Код отправлен в Telegram." });
    }

    if (body.action === "verify") {
      const code = String(body.code || "").replace(/\D/g, "");
      if (!/^\d{6}$/.test(code)) return json(400, { ok: false, error: "Введите шестизначный код." });
      if (!old) return json(400, { ok: false, error: "Сначала запросите код в Telegram." });
      if (new Date(old.expires_at).getTime() < now) return json(400, { ok: false, error: "Код истёк. Запросите новый через 5 минут." });
      if (Number(old.attempts || 0) >= 5) return json(429, { ok: false, error: "Слишком много попыток. Запросите новый код позже." });
      if (await sha256(code) !== old.code_hash) {
        await rest(`${table}?telegram_id=eq.${tg.id}`, serviceKey, {
          method: "PATCH", body: JSON.stringify({ attempts: Number(old.attempts || 0) + 1 }),
        });
        return json(400, { ok: false, error: "Неверный код." });
      }

      const username = String(old.username);
      const passwordHash = String(old.password_hash);
      const collision = await rest(`app_users?username=ilike.${encodeURIComponent(username)}&select=id,telegram_id&limit=2`, serviceKey);
      if (Array.isArray(collision) && collision.some((x: any) => Number(x.telegram_id) !== tg.id)) {
        return json(409, { ok: false, error: "Этот логин уже занят. Запросите код заново с другим логином." });
      }

      const existing = await rest(`app_users?telegram_id=eq.${tg.id}&select=*`, serviceKey);
      let users;
      const fields = { username, password_hash: passwordHash, telegram_id: tg.id, last_seen_at: new Date().toISOString() };
      if (Array.isArray(existing) && existing.length) {
        users = await rest(`app_users?id=eq.${existing[0].id}`, serviceKey, { method: "PATCH", body: JSON.stringify(fields) });
      } else {
        users = await rest("app_users", serviceKey, {
          method: "POST", body: JSON.stringify({
            id: crypto.randomUUID(), ...fields, banned: false, is_admin: false,
            created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
          }),
        });
      }
      const user = Array.isArray(users) ? users[0] : users;
      if (!user || user.banned) return json(403, { ok: false, error: "Регистрация недоступна для этого аккаунта." });
      await rest(`${table}?telegram_id=eq.${tg.id}`, serviceKey, { method: "DELETE" });
      return json(200, { ok: true, user: publicUser(user) });
    }

    return json(400, { ok: false, error: "Неизвестное действие." });
  } catch (e) {
    return json(400, { ok: false, error: e instanceof Error ? e.message : "Ошибка регистрации." });
  }
});
