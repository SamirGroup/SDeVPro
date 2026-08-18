<p align="center">
  <img src=".github/logo.png" alt="SDeVPro" width="220">
</p>

<div align="center">

# SDeVPro

### AI yordamida avtonom xavfsizlik tekshiruvi va monitoring platformasi

</div>

---

## Loyiha haqida

**SDeVPro** — to'liq mahalliy (on-premise) ishlaydigan, AI-asoslangan
xavfsizlik tekshiruvi va monitoring platformasi. Litsenziya va kelib chiqish
tarixi haqida to'liq ma'lumot [NOTICE](NOTICE) faylida keltirilgan. Asosiy
xususiyatlari:

- **Docker talab qilinmaydi.** Asosiy mahsulot — `sdevpro/` paketidagi
  skanerlash motori — to'g'ridan-to'g'ri Python orqali, hech qanday
  konteyner yoki tashqi sandbox'siz ishlaydi.
- **Hech qanday tashqi xizmatga ulanmaydi.** SDeVPro faqat (a) siz kiritgan
  AI provayder (OpenAI/Anthropic/Gemini va h.k.) bilan to'g'ridan-to'g'ri, va
  (b) tekshirilayotgan nishonning o'zi bilan aloqa qiladi. Hech qanday
  telemetriya, analitika yoki uchinchi tomon "xavfsizlik platformasi"ga
  ma'lumot yuborilmaydi.
- **Har bir foydalanuvchi o'z AI tokeni bilan ishlaydi.** Token shifrlangan
  holda saqlanadi va faqat o'sha foydalanuvchining so'rovlari uchun
  ishlatiladi.
- **Telegram bot orqali ishlaydi.** Mijoz o'z tizimini (sayt, API, server,
  yoki GitHub repository) botga yuboradi — bot to'liq tekshiruv o'tkazadi, AI
  yordamida xulosa va tuzatish yo'riqnomasi beradi, va xohlasa belgilangan
  vaqt oralig'ida (masalan har soatda) avtomatik qayta tekshirib, hisobot
  yuborib turadi. Interfeys 3 tilda: o'zbek, rus, ingliz.
- **Server-log tahlili.** Mijoz o'z server logini yuborsa, bot undan shubhali
  IP manzillar va hujum urinishlarini (SQLi, XSS, brute-force va h.k.)
  ajratib beradi.
- **GitHub repository skaneri.** Ochiq yoki (token bilan) yopiq repolarni
  klonlab, kod ichidagi maxfiy kalitlar va xavfli naqshlarni tekshiradi.

Kod bazasi ichki texnik sabablarga ko'ra ikkita Python paketidan iborat:
`sdevpro/` (asosiy, Docker'siz, yangi dvigatel) va `strix/` (ichki modul
nomi — asl ko'p-agentli, Docker-sandbox asosidagi chuqur tekshiruv mexanizmi;
foydalanuvchiga ko'rinmaydi, hech qanday tashqi xizmatga ulanmaydi va
standart ishga tushirishda ishlatilmaydi). Ikkalasi ham to'liq mustaqil —
`sdevpro/` paketi `strix/` papkasini import qilmaydi.

> [!WARNING]
> **Faqat vakolat berilgan tekshiruvlar uchun.** SDeVPro sizga ko'rsatgan
> nishonlarni real ravishda tekshiradi/hujum qiladi. Faqat o'zingizga
> tegishli yoki tekshirish uchun yozma ruxsatga ega bo'lgan tizimlarni
> tekshiring. Ruxsatsiz tekshiruv ko'p mamlakatlarda jinoiy javobgarlikka
> sabab bo'ladi. Botning har bir mijozi tekshiruvdan oldin buni tasdiqlashi
> shart (`/scan` buyrug'i shu tasdiqni so'raydi).

---

## Tez boshlash (Windows, Docker'siz)

### 1. Talablar

- Python 3.12+ (loyiha `.venv/` da Python 3.14 bilan sinovdan o'tkazilgan)
- Telegram bot tokeni ([@BotFather](https://t.me/BotFather) orqali oling: `/newbot`)
- LLM API kaliti (Anthropic, OpenAI, Gemini va h.k. — istalgan biri)

### 2. O'rnatish

PowerShell'da loyiha papkasida:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[sdevpro]"
```

> Faqat Telegram bot dvigateliga kerakli paketlarni o'rnatish uchun (original
> `strix` CLI'ning og'ir bog'liqliklarisiz, tezroq):
> ```powershell
> pip install litellm requests reportlab "python-telegram-bot[job-queue]" dnspython beautifulsoup4 python-dotenv
> ```

### 3. Sozlash

```powershell
copy .env.example .env
notepad .env
```

`.env` faylida kamida quyidagilarni to'ldiring:

```
TELEGRAM_BOT_TOKEN=123456:ABC-...
SDEVPRO_LLM=anthropic/claude-sonnet-4-6
SDEVPRO_LLM_API_KEY=sk-...
```

Birinchi marta ishga tushirishda **albatta** `SDEVPRO_ALLOWED_USERS` ni
o'zingizning Telegram ID'ingiz bilan to'ldiring (bo'sh qoldirsangiz — botga
yozgan HAR KIM undan foydalana oladi va sizning nomingizdan tashqi
tizimlarni "tekshirishi" mumkin bo'lib qoladi). ID'ni bilish uchun Telegram'da
[@userinfobot](https://t.me/userinfobot) ga yozing.

### 4. Ishga tushirish

```powershell
sdevpro-bot
```

yoki:

```powershell
python -m sdevpro.main
```

Botni doimiy (kompyuter qayta yoqilganda ham) ishlashi uchun Windows Task
Scheduler'da "At startup" trigger bilan shu buyruqni ishga tushiruvchi vazifa
yarating (`scripts/run_bot.ps1` shablonini ishlating), yoki `nssm`/`pm2`
kabi vosita bilan Windows xizmati sifatida o'rnating.

---

## Telegram botidan foydalanish

| Buyruq | Tavsif |
|---|---|
| `/start` | Xush kelibsiz xabari va logotip |
| `/scan <manzil>` | Bir martalik to'liq tekshiruv (masalan `/scan https://example.com`) |
| `/schedule <manzil> <interval>` | Davriy tekshiruv, masalan `/schedule https://example.com 1h` |
| `/unschedule <manzil>` | Davriy tekshiruvni bekor qilish |
| `/myschedules` | Faol davriy tekshiruvlar ro'yxati |
| `/report` | Oxirgi hisobotni qayta (PDF bilan) olish |
| *.log / .txt fayl yuborish* | Server log fayli asosida hujum-manba tahlili |

Har bir tekshiruv quyidagilarni o'z ichiga oladi:

1. **Recon** — DNS, ochiq portlar, HTTP sarlavhalar, TLS sertifikat holati,
   texnologiya (CMS/freymvork) aniqlash.
2. **Web probelar** — xavfsizlik sarlavhalari, cookie flaglar, CORS
   konfiguratsiyasi, clickjacking, ochiq redirect, reflected XSS, SQL
   Injection (xato-asoslangan), oshkor bo'lib qolgan maxfiy fayllar
   (`.git`, `.env`, backup fayllar va h.k.).
3. **Kod skaneri** (mahalliy papka berilsa — whitebox rejim) — maxfiy
   kalitlar (AWS/GitHub/Slack tokenlari), xavfli kod naqshlari (`eval`,
   `os.system`, xom SQL-concatenation va h.k.).
4. **AI tahlili** — barcha topilmalarni ustuvorlik bo'yicha saralaydi, har
   biriga CVSS baho, hujum stsenariysi va aniq tuzatish yo'riqnomasi yozadi,
   umumiy holat xulosasi va tizim darajasidagi himoya tavsiyalarini beradi.
5. **Hisobot** — Telegram xabarlari (real vaqtda) + to'liq PDF fayl.

AI hech qachon dalilsiz yangi "topilma" o'ylab topmaydi — u faqat real
probelar aniqlagan holatlarni tushuntiradi va ustuvorlashtiradi.

---

## Loyiha tuzilishi

```
SDeVPro/
├── sdevpro/            # Yangi, Docker'siz asosiy mahsulot
│   ├── scanner/        # recon, web probe, kod skaneri
│   ├── ai_analyst.py   # LLM-asoslangan triage/hisobot generatsiyasi
│   ├── reporter.py     # Telegram matn + PDF hisobot
│   ├── log_analyzer.py # Server-log hujum-manba tahlili
│   ├── telegram_bot.py # Bot buyruqlari, jadval (schedule), consent
│   ├── storage.py      # JSON-asoslangan saqlash (schedule/tarix)
│   └── config.py       # .env orqali sozlash
├── sdevpro/              # Original ko'p-agentli dvigatel (Docker-asoslangan,
│                        # ma'lumot/kengaytirilgan rejim sifatida saqlangan)
├── .env.example
└── NOTICE               # Apache-2.0 talabiga ko'ra o'zgarishlar ro'yxati
```

## Litsenziya

Apache License 2.0 — [LICENSE](LICENSE) faylini ko'ring. Ushbu loyiha
Strix'ning hosila (derivative) ishi — [NOTICE](NOTICE) faylida original
mualliflik huquqi va barcha o'zgarishlar ro'yxati saqlangan.
