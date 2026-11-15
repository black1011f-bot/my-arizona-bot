import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const MANAGER = new Set(["bounqy31", "bounqy"]);
const SERVERS = ["🔥 Phoenix","🌴 Tucson","🌵 Scottdale","⚜️ Chandler","❄️ Brainburg","🌊 Yuma","✨ Saint-Rose","🏛 Mesa","❤️ Red-Rock","🍀 Surprise","⚡️ Prescott","🌲 Glendale","👑 Kingman","⚓️ Winslow","🌴 Payson","💎 Gilbert","🔥 Show-Low","🌴 Casa-Grande","📜 Page","☀️ Sun-City","👑 Queen-Creek","🌵 Sedona","🎄 Holiday","🍀 Wednesday","⚡️ Yava","🌌 Faraway","🎁 Christmas","🐝 Bumble Bee","🪞 Mirage","💖 Love","📱 Mobile I","📱 Mobile II","📱 Mobile III"];
const CATS = ["💍 Аксессуары и вещи","🚗 Транспорт и тюнинг","👕 Скины и охранники","🏠 Недвижимость и бизнесы","📦 Ресурсы и материалы"];
const HEAD = {"Content-Type":"application/json"};
const reply = (body: unknown, status=200) => new Response(JSON.stringify(body),{status,headers:HEAD});
async function db(path:string, method="GET", body?:unknown, prefer="return=representation") {
 const r=await fetch(`${SUPABASE_URL}/rest/v1/${path}`,{method,headers:{apikey:SERVICE,Authorization:`Bearer ${SERVICE}`,...HEAD,Prefer:prefer},body:body===undefined?undefined:JSON.stringify(body)});
 const t=await r.text(); let d:any; try{d=t?JSON.parse(t):null}catch{d=t}
 if(!r.ok) throw new Error(d?.message||d?.details||String(t)); return d;
}
async function tg(method:string,payload:Record<string,unknown>) {
 const r=await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/${method}`,{method:"POST",headers:HEAD,body:JSON.stringify(payload)});
 const d=await r.json(); if(!d.ok) throw new Error(d.description||"Telegram API error"); return d.result;
}
const send=(chat_id:number,text:string,reply_markup?:unknown)=>tg("sendMessage",{chat_id,text,parse_mode:"HTML",...(reply_markup?{reply_markup}:{})});
const kb=(rows:string[][])=>({keyboard:rows.map(row=>row.map(text=>({text}))),resize_keyboard:true});
const inline=(rows:{text:string,callback_data:string}[][])=>({inline_keyboard:rows.map(row=>row.map(x=>({text:x.text,callback_data:x.callback_data})))});
const mainKb=kb([["📤 Продать товар","📥 Скупить товар"],["🔍 Поиск объявлений","📋 Мои объявления"],["🌐 Сменить сервер","👑 VIP"],["🎁 Бонусы и рефералы","❓ Помощь"]]);
async function state(uid:number) { const a=await db(`bot_user_states?telegram_user_id=eq.${uid}&select=state`); return a?.[0]?.state||{}; }
async function setState(uid:number,s:Record<string,unknown>) { await db("bot_user_states?on_conflict=telegram_user_id","POST",{telegram_user_id:uid,state:s,updated_at:new Date().toISOString()},"resolution=merge-duplicates,return=minimal"); }
async function clearState(uid:number){await setState(uid,{});}
async function user(from:any) {
 const id=Number(from.id), rows=await db(`app_users?telegram_id=eq.${id}&select=*&limit=1`);
 if(rows?.[0]) return rows[0];
 const created=await db("app_users","POST",{username:String(from.username||("tg_"+id)).toLowerCase().slice(0,20),telegram_id:id,first_name:from.first_name||null,last_name:from.last_name||null,language_code:from.language_code||"ru"});
 return created?.[0];
}
async function banned(uid:number) { const u=await db(`app_users?telegram_id=eq.${uid}&select=banned&limit=1`); return !!u?.[0]?.banned; }
function price(v:string) { const x=v.toLowerCase().replace(/\\s/g,"").replace(",","."); const m=x.match(/^([0-9]+(?:\\.[0-9]+)?)(ккк|кк|к|млн|млрд)?$/); if(!m) return NaN; return Math.round(Number(m[1])*({к:1e3,кк:1e6,ккк:1e9,млн:1e6,млрд:1e9}[m[2]||""]||1)); }
function money(v:number){return v>=1e9?(v/1e9)+"ккк":v>=1e6?(v/1e6)+"кк":v>=1e3?(v/1e3)+"к":String(v)}
async function handleMessage(m:any) {
 const chat=Number(m.chat.id), from=m.from, uid=Number(from.id), text=String(m.text||"");
 const u=await user(from); if(!u) return send(chat,"⚠️ Не удалось создать профиль.");
 if(await banned(uid)) return send(chat,"⛔ Ваш аккаунт заблокирован.");
 const s=await state(uid);
 if(text==="/start"||text.startsWith("/start ")) {
  await clearState(uid);
  await db(`app_users?telegram_id=eq.${uid}`,"PATCH",{server:u.server||SERVERS[0],last_seen_at:new Date().toISOString()});
  return send(chat,`👋 <b>ARZstore — объявления Arizona RP</b>\n🌐 Сервер: ${u.server||SERVERS[0]}\n\nВыберите действие:`,mainKb);
 }
 if(text==="/help"||text==="❓ Помощь") return send(chat,"Команды: /start — меню, /help — помощь. Вы можете публиковать объявления о продаже и скупке, искать товары и управлять своими объявлениями.",mainKb);
 if(text==="❌ Отменить действие"||text==="/cancel"){await clearState(uid);return send(chat,"Действие отменено.",mainKb);}
 if(text==="🌐 Сменить сервер"){await setState(uid,{step:"server"});return send(chat,"Выберите сервер:",kb(SERVERS.reduce((a,v,i)=>{(a[Math.floor(i/2)]??=[]).push(v);return a},[] as string[][]).concat([["⬅️ Назад"]])));}
 if(s.step==="server"){if(SERVERS.includes(text)){await db(`app_users?telegram_id=eq.${uid}`,"PATCH",{server:text});await clearState(uid);return send(chat,"Сервер изменён: "+text,mainKb);} }
 if(text==="👑 Админ-панель"||text==="/admin"){
  if(!MANAGER.has(String(from.username||"").toLowerCase()))return send(chat,"⛔ Доступ запрещён.");
  return send(chat,"👑 <b>Панель модерации</b>",kb([["модерация продажи","модерация скупки"],["📊 Статистика","⬅️ Назад"]]));
 }
 if(text==="модерация продажи"||text==="модерация скупки"){
  if(!MANAGER.has(String(from.username||"").toLowerCase()))return send(chat,"⛔ Доступ запрещён.");
  const mode=text==="модерация скупки"?"buy":"sell";
  const pending=await db(`ads?status=eq.pending&mode=eq.${mode}&select=id,item_name,description,price,server,author_id&order=created_at.asc&limit=10`);
  if(!pending?.length)return send(chat,"📭 Нет объявлений на модерации.");
  for(const ad of pending)await send(chat,`#${ad.id} · ${ad.server}\\n<b>${ad.item_name}</b>\\n${ad.description||""}\\nЦена: ${money(Number(ad.price||0))}`,inline([[{text:"✅ Одобрить",callback_data:"approve:"+ad.id},{text:"❌ Отклонить",callback_data:"reject:"+ad.id}]]));
  return;
 }
 if(text==="📊 Статистика"&&MANAGER.has(String(from.username||"").toLowerCase())){
  const counts=await db("ads?select=status");const pending=(counts||[]).filter((x:any)=>x.status==="pending").length;return send(chat,`📊 Всего объявлений: ${counts?.length||0}\\n⏳ На модерации: ${pending}`);
 }
 if(text==="📤 Продать товар"||text==="📥 Скупить товар"){await setState(uid,{step:"category",mode:text.includes("Скупить")?"buy":"sell",images:[]});return send(chat,"Выберите категорию:",kb(CATS.map(x=>[x]).concat([["❌ Отменить действие"]])));}
 if(s.step==="category"&&CATS.includes(text)){await setState(uid,{...s,step:"price",category:text});return send(chat,"Введите цену (например 150к, 2.5кк):",kb([["❌ Отменить действие"]]));}
 if(s.step==="price"){const n=price(text);if(!Number.isSafeInteger(n)||n<0||n>1e12)return send(chat,"Некорректная цена. Пример: 150к или 2.5кк.");await setState(uid,{...s,step:"name",price:n});return send(chat,"Введите название товара (до 100 символов):");}
 if(s.step==="name"){if(text.trim().length<2)return send(chat,"Название слишком короткое.");await setState(uid,{...s,step:"description",item_name:text.trim().slice(0,100)});return send(chat,"Введите описание (до 2000 символов):");}
 if(s.step==="description"){if(text.length>2000)return send(chat,"Описание слишком длинное.");if(/хуй|пизд|еба|бля|сука|залуп/i.test(text))return send(chat,"🤬 В описании обнаружены запрещённые слова.");const ad=await db("ads","POST",{author_id:u.id,author_username:from.username||String(uid),server:u.server||SERVERS[0],category:s.category,item_name:s.item_name,description:text,price:s.price,images:"[]",mode:s.mode,status:"pending",hidden:false});
 await clearState(uid);await send(chat,"✅ Объявление отправлено на модерацию. После проверки придёт уведомление.",mainKb);
 const admins=await db("admin_chats?select=chat_id");const p=ad?.[0];if(p)for(const a of admins||[])await send(Number(a.chat_id),`🆕 <b>Объявление на модерацию</b>\n#${p.id}\n${p.server}\n${p.item_name}\nЦена: ${money(Number(p.price))}\n${p.description}`,inline([[{text:"✅ Одобрить",callback_data:"approve:"+p.id},{text:"❌ Отклонить",callback_data:"reject:"+p.id}]] )).catch(()=>{});
 return;
 }
 if(text==="🔍 Поиск объявлений"){await setState(uid,{step:"search"});return send(chat,"Введите название или ключевое слово:");}
 if(s.step==="search"){await clearState(uid);const term=text.replace(/[,%]/g," ").trim();const ads=await db(`ads?status=eq.approved&hidden=eq.false&server=eq.${encodeURIComponent(u.server||SERVERS[0])}&or=(item_name.ilike.*${encodeURIComponent(term)}*,description.ilike.*${encodeURIComponent(term)}*)&select=id,item_name,description,price,author_username,mode&limit=5`);if(!ads?.length)return send(chat,"Ничего не найдено.",mainKb);for(const a of ads)await send(chat,`#${a.id}\n<b>${a.item_name}</b>\n${a.description||""}\nЦена: ${money(Number(a.price||0))}\nАвтор: @${a.author_username||"—"}\nТип: ${a.mode==="buy"?"скупка":"продажа"}`);return;}
 if(text==="📋 Мои объявления"){const ads=await db(`ads?author_id=eq.${u.id}&select=id,item_name,price,status,mode&order=created_at.desc&limit=10`);if(!ads?.length)return send(chat,"Объявлений пока нет.",mainKb);for(const a of ads)await send(chat,`#${a.id} ${a.item_name}\n${money(Number(a.price||0))} · ${a.status==="pending"?"⏳ На модерации":a.status==="approved"?"✅ Опубликовано":"🗑 Удалено"}`,inline([[{text:"🗑 Удалить",callback_data:"delete:"+a.id}]]));return;}
 if(text==="👑 VIP"){const prem=await db(`premium_users?user_id=eq.${u.id}&select=expires_at`);const exp=prem?.[0]?.expires_at;return send(chat,exp&&Number(exp)>Date.now()/1000?"👑 VIP активен до "+new Date(Number(exp)*1000).toLocaleString("ru-RU"):"VIP не активен. Информация о покупке: @bounqy31",mainKb);}
 if(text==="🎁 Бонусы и рефералы"){const bonus=await db(`user_bonuses?user_id=eq.${u.id}&select=vip_ads_count`);return send(chat,`🎁 Бонусные VIP-публикации: ${bonus?.[0]?.vip_ads_count||0}\nВаша ссылка: https://t.me/arizona_coin_bot?start=ref_${uid}`,mainKb);}
 if(text==="⬅️ Назад")return send(chat,"Главное меню:",mainKb);
 if(text==="Готово")return send(chat,"Нет ожидающего действия.",mainKb);
 return send(chat,"Выберите действие в меню или отправьте /help.",mainKb);
}
async function handleCallback(q:any) {
 const data=String(q.data||""), uid=Number(q.from.id), chat=Number(q.message?.chat?.id);await tg("answerCallbackQuery",{callback_query_id:q.id});
 if(data.startsWith("approve:")||data.startsWith("reject:")) {
  const uname=String(q.from.username||"").toLowerCase();if(!MANAGER.has(uname)){return send(chat,"⛔ Нет прав.");}
  const [act,id]=data.split(":");const rows=await db(`ads?id=eq.${encodeURIComponent(id)}&select=*`);const ad=rows?.[0];if(!ad)return send(chat,"Объявление не найдено.");
  if(act==="approve"){await db(`ads?id=eq.${encodeURIComponent(id)}`,"PATCH",{status:"approved",expires_at:new Date(Date.now()+48*3600000).toISOString()});await send(Number((await db(`app_users?id=eq.${ad.author_id}&select=telegram_id`))?.[0]?.telegram_id||0),`✅ Объявление «${ad.item_name}» одобрено.`).catch(()=>{});return send(chat,"✅ Объявление одобрено.");}
  await db(`ads?id=eq.${encodeURIComponent(id)}`,"PATCH",{status:"rejected"});return send(chat,"❌ Объявление отклонено.");
 }
 if(data.startsWith("delete:")){const id=data.slice(7);const u=(await db(`app_users?telegram_id=eq.${uid}&select=id`))?.[0];const ad=(await db(`ads?id=eq.${encodeURIComponent(id)}&select=author_id`))?.[0];if(u&&ad?.author_id===u.id){await db(`ads?id=eq.${encodeURIComponent(id)}`,"PATCH",{status:"deleted",hidden:true});return send(chat,"Объявление удалено.");}}
}
Deno.serve(async(req:Request)=>{
 if(req.method==="GET"){
  const url=new URL(req.url);
  if(url.searchParams.get("setup")==="webhook"){
   if(!BOT_TOKEN)return reply({ok:false,error:"TELEGRAM_BOT_TOKEN is missing"},503);
   const webhookUrl=`${SUPABASE_URL}/functions/v1/telegram-bot`;
   const response=await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/setWebhook`,{method:"POST",headers:HEAD,body:JSON.stringify({url:webhookUrl,allowed_updates:["message","callback_query"],drop_pending_updates:false})});
   const result=await response.json();
   if(!response.ok||!result.ok)return reply({ok:false,error:result.description||"Telegram setWebhook failed"},502);
   const info=await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo`);
   const status=await info.json();
   return reply({ok:true,webhook_set:true,webhook_url:webhookUrl,pending_update_count:status.result?.pending_update_count||0});
  }
  return reply({ok:true,service:"ARZstore Telegram bot",status:"active"});
 }
 if(req.method!=="POST")return reply({ok:false,error:"Method not allowed"},405);
 if(!BOT_TOKEN||!SERVICE||!SUPABASE_URL)return reply({ok:false,error:"Missing Supabase/Telegram secrets"},503);
 try{
  const update=await req.json();const updateId=Number(update.update_id);
  if(Number.isFinite(updateId)){try{await db("bot_event_logs","POST",{update_id:updateId,event_type:update.message?"message":"callback",telegram_user_id:update.message?.from?.id||update.callback_query?.from?.id||null,chat_id:update.message?.chat?.id||update.callback_query?.message?.chat?.id||null,username:update.message?.from?.username||update.callback_query?.from?.username||null,callback_data:update.callback_query?.data||null,outcome:"received"},"return=minimal");}catch(e){if(String(e).includes("duplicate")||String(e).includes("unique"))return reply({ok:true,duplicate:true});}}
  if(update.message)await handleMessage(update.message);
  if(update.callback_query)await handleCallback(update.callback_query);
  return reply({ok:true});
 }catch(e){console.error(e);return reply({ok:false,error:e instanceof Error?e.message:"Internal error"},500);}
});
