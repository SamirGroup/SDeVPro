"""Minimal i18n layer: Uzbek / Russian / English strings for the Telegram bot.

Usage: ``t(lang, "key", name="value")`` — falls back to Uzbek, then to the
raw key, if a translation or language is missing, so a missing string never
crashes the bot.
"""

from __future__ import annotations

SUPPORTED_LANGUAGES = ("uz", "ru", "en")
DEFAULT_LANGUAGE = "uz"

LANGUAGE_LABELS = {
    "uz": "O'zbekcha",
    "ru": "Русский",
    "en": "English",
}

SEVERITY_LABELS: dict[str, dict[str, str]] = {
    "uz": {"critical": "KRITIK", "high": "YUQORI", "medium": "O'RTA", "low": "PAST", "info": "MA'LUMOT"},
    "ru": {"critical": "КРИТИЧНО", "high": "ВЫСОКИЙ", "medium": "СРЕДНИЙ", "low": "НИЗКИЙ", "info": "ИНФО"},
    "en": {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "low": "LOW", "info": "INFO"},
}  # fmt: skip

_TR: dict[str, dict[str, str]] = {
    "uz": {
        "choose_language": "Tilni tanlang / Выберите язык / Choose language:",
        "language_set": "Til o'zbekchaga o'rnatildi. /help buyrug'i orqali to'liq yo'riqnomani ko'rishingiz mumkin.",
        "welcome": (
            "SDeVPro Xavfsizlik Botiga xush kelibsiz!\n\n"
            "Men sizning tizimingizni (veb-sayt, API yoki GitHub repository) AI yordamida "
            "xavfsizlik bo'yicha tekshiruvdan o'tkazaman: zaifliklarni topaman, ularni qanday "
            "tuzatish kerakligini tushuntiraman va xohlasangiz belgilangan vaqt oralig'ida "
            "avtomatik hisobot yuboraman.\n\n"
            "Ishni boshlashdan oldin o'zingizning AI (LLM) API tokeningizni kiriting: /setkey\n"
            "To'liq yo'riqnoma uchun: /help"
        ),
        "help": (
            "SDeVPro — to'liq qo'llanma\n\n"
            "1) AVVAL AI TOKEN KIRITING\n"
            "   /setkey — o'zingizning OpenAI/Anthropic/Gemini/DeepSeek va h.k. API tokeningizni "
            "kiritasiz. Har bir foydalanuvchi o'z tokeni bilan ishlaydi, token shifrlangan holda "
            "saqlanadi va faqat siz uchun ishlatiladi.\n"
            "   Token qayerdan olinadi — /aitoken\n\n"
            "2) TEKSHIRUV BUYRUQLARI\n"
            "   /scan <manzil> — bir martalik to'liq tekshiruv.\n"
            "     Masalan: /scan https://example.com\n"
            "     Yoki GitHub repo: /scan https://github.com/foo/bar\n"
            "   /schedule <manzil> <interval> — davriy tekshiruv (masalan har soatda).\n"
            "     Masalan: /schedule https://example.com 1h\n"
            "   /unschedule <manzil> — davriy tekshiruvni bekor qilish.\n"
            "   /myschedules — faol davriy tekshiruvlar ro'yxati.\n"
            "   /report — oxirgi hisobotni qayta olish (matn + PDF/TXT hujjat).\n\n"
            "3) SERVER LOG TAHLILI\n"
            "   .log yoki .txt faylini botga yuboring — men undan shubhali IP manzillar va "
            "hujum urinishlarini aniqlab, to'liq hisobot beraman (matn + yuklab olinadigan hujjat).\n\n"
            "4) GITHUB REPOSITORY\n"
            "   Ochiq (public) repolarni to'g'ridan-to'g'ri /scan orqali tekshirsa bo'ladi.\n"
            "   Yopiq (private) repo uchun: /setgithubtoken <token> — GitHub token qanday "
            "olinishi haqida /githubtoken buyrug'ida yozilgan.\n\n"
            "5) SOZLAMALAR\n"
            "   /language — interfeys tilini o'zgartirish (uz/ru/en).\n"
            "   /mysettings — joriy sozlamalaringiz (til, token holati).\n"
            "   /deletekey — saqlangan AI tokenni o'chirish.\n\n"
            "MUHIM: faqat o'zingizga tegishli yoki tekshirishga yozma ruxsatingiz bo'lgan "
            "tizimlarni tekshiring."
        ),
        "aitoken_help": (
            "AI (LLM) API token qayerdan olinadi:\n\n"
            "• Anthropic (Claude): console.anthropic.com -> Settings -> API Keys -> Create Key\n"
            "  Format: /setkey anthropic/claude-sonnet-4-6 sk-ant-...\n\n"
            "• OpenAI (GPT): platform.openai.com/api-keys -> Create new secret key\n"
            "  Format: /setkey openai/gpt-5.4 sk-...\n\n"
            "• Google Gemini: aistudio.google.com/app/apikey -> Create API key\n"
            "  Format: /setkey gemini/gemini-3-pro-preview AIza...\n\n"
            "• DeepSeek: platform.deepseek.com/api_keys\n"
            "  Format: /setkey deepseek/deepseek-v4-pro sk-...\n\n"
            "Tokeningiz shifrlangan holda saqlanadi va faqat sizning so'rovlaringiz uchun "
            "ishlatiladi — boshqa hech kimga ko'rinmaydi."
        ),
        "setkey_usage": (
            "Foydalanish: /setkey <provider>/<model> <api_token>\n"
            "Masalan: /setkey anthropic/claude-sonnet-4-6 sk-ant-xxxxxxxx\n"
            "Provider/model ro'yxati va token olish yo'llari uchun: /aitoken"
        ),
        "setkey_saved": "AI token saqlandi. Model: {model}. Endi /scan orqali tekshiruvni boshlashingiz mumkin.",
        "deletekey_done": "AI tokeningiz o'chirildi.",
        "deletekey_none": "Sizda saqlangan AI token yo'q edi.",
        "no_api_key": (
            "Sizda hali AI token o'rnatilmagan. Avval /setkey buyrug'i orqali o'z tokeningizni "
            "kiriting (yo'riqnoma: /aitoken)."
        ),
        "mysettings": "Til: {language}\nAI model: {model}\nGitHub token: {github_token_status}",
        "github_token_set": "o'rnatilgan",
        "github_token_unset": "o'rnatilmagan",
        "setgithubtoken_usage": "Foydalanish: /setgithubtoken <token>",
        "setgithubtoken_saved": "GitHub token saqlandi — endi yopiq (private) repolarni ham tekshirishim mumkin.",
        "githubtoken_help": (
            "Yopiq (private) GitHub repo'ni tekshirish uchun Personal Access Token kerak:\n"
            "github.com -> Settings -> Developer settings -> Personal access tokens -> "
            "Fine-grained tokens -> faqat 'Contents: Read-only' huquqi bilan yarating.\n"
            "Keyin: /setgithubtoken <token>"
        ),
        "consent_prompt": (
            "Tekshiruvni boshlashdan oldin tasdiqlang:\n\n"
            "Men ushbu manzilning (yoki tizimning) egasiman, yoki uni xavfsizlik tekshiruvidan "
            "o'tkazish uchun yozma ruxsatga egaman, va bu tekshiruv natijalari uchun to'liq "
            "javobgarlikni o'z zimmamga olaman."
        ),
        "consent_button": "Ha, vakolatim bor — boshlash",
        "consent_confirmed": "Tasdiqlandi. Tekshiruv boshlanmoqda...",
        "scan_usage": "Foydalanish: /scan <manzil>\nMasalan: /scan https://example.com",
        "scan_started": "Tekshiruv boshlandi: {target}\n\nRecon boshlanmoqda...",
        "scan_progress": "Tekshiruv davom etmoqda: {target}\n\n{message}",
        "scan_done_preparing": "Tekshiruv tugadi. Hisobot tayyorlanmoqda...",
        "schedule_usage": (
            "Foydalanish: /schedule <manzil> <interval>\n"
            "Masalan: /schedule https://example.com 1h\n"
            "Interval: '30m', '1h', '2h30m' yoki daqiqada butun son."
        ),
        "schedule_bad_interval": "Interval noto'g'ri yoki juda qisqa (kamida 5 daqiqa bo'lishi kerak).",
        "schedule_needs_consent": "Avval /scan orqali kamida bitta tekshiruv qilib, vakolatni tasdiqlang, so'ng /schedule buyrug'ini qayta yuboring.",
        "schedule_set": "Davriy tekshiruv o'rnatildi: {target}\nHar {minutes} daqiqada avtomatik hisobot yuboriladi.",
        "unschedule_usage": "Foydalanish: /unschedule <manzil>",
        "unschedule_done": "Davriy tekshiruv bekor qilindi.",
        "unschedule_none": "Bunday davriy tekshiruv topilmadi.",
        "myschedules_none": "Faol davriy tekshiruvlar yo'q.",
        "myschedules_header": "Faol davriy tekshiruvlar:",
        "myschedules_item": "- {target} (har {minutes} daqiqada)",
        "report_none": "Hozircha saqlangan hisobot yo'q. Avval /scan orqali tekshiruv qiling.",
        "denied": "Kechirasiz, sizda bu botdan foydalanish uchun ruxsat yo'q.",
        "doc_only_log": "Faqat .log yoki .txt formatidagi server log fayllarini qabul qilaman.",
        "doc_too_big": "Fayl juda katta (20MB dan oshmasin).",
        "doc_analyzing": "Log fayli tahlil qilinmoqda...",
        "unexpected_error": "Kutilmagan xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.",
        "scheduled_scan_failed": "Davriy tekshiruvda xatolik yuz berdi ({target}). Keyinroq qayta urinib ko'riladi.",
        "report_summary_title": "SDeVPro — Xavfsizlik Skanerlash Hisoboti",
        "report_target": "Nishon: {target}",
        "report_mode": "Rejim: {mode} | {kind}",
        "report_kind_whitebox": "Kod tekshiruvi",
        "report_kind_github": "GitHub repository",
        "report_kind_blackbox": "Tashqi (blackbox)",
        "report_started": "Boshlandi: {time}",
        "report_finished": "Tugadi: {time}",
        "report_findings_summary": "Topilmalar bo'yicha xulosa:",
        "report_no_findings": "  Hech qanday topilma yo'q.",
        "report_error": "[!] Skanerlash davomida xatolik: {error}",
        "report_ai_summary": "AI xulosasi:",
        "report_defense_title": "SDeVPro — Umumiy Himoya Tavsiyalari",
        "finding_category": "Kategoriya: {value}",
        "finding_location": "Joylashuv: {value}",
        "finding_description": "Tavsif: {value}",
        "finding_attack_vector": "Hujum vektori: {value}",
        "finding_remediation": "Tuzatish: {value}",
        "pdf_caption": "To'liq PDF hisobot",
        "txt_caption": "To'liq matnli hisobot (.txt)",
        "no_git": "Git dasturi serverda o'rnatilmagan — GitHub repolarni tekshirib bo'lmaydi. Administratorga xabar bering.",
        "github_clone_failed": "Repository'ni yuklab bo'lmadi (manzil noto'g'ri, yopiq repo yoki token kerak bo'lishi mumkin). Yopiq repo bo'lsa: /githubtoken",
        "progress_recon_started": "Recon boshlandi: {target}",
        "progress_recon_done": "Recon tugadi: {ports} ochiq port, {tech} texnologiya aniqlandi.",
        "progress_codescan_started": "Manba kod tekshirilmoqda (secrets, xavfli naqshlar)...",
        "progress_codescan_done": "Kod skanerlash tugadi: {files} fayl tekshirildi.",
        "progress_webprobe_started": "Web zaifliklar tekshirilmoqda (XSS, SQLi, CORS, maxfiy fayllar)...",
        "progress_webprobe_done": "Web probe tugadi: {count} topilma.",
        "progress_ai_analyzing": "AI tahlilchisi topilmalarni baholamoqda...",
        "progress_ai_done": "AI tahlili tugadi.",
        "progress_github_cloning": "GitHub repository yuklab olinmoqda: {target}",
        "progress_github_cloned": "Repository yuklandi, kod tekshirilmoqda...",
        "ai_failed_fallback": "AI tahlili muvaffaqiyatsiz tugadi; quyida xom (AI ishlov bermagan) topilmalar keltirilgan.",
        "log_report_title": "SDeVPro — Server Log Hujum Tahlili",
        "log_report_totals": "Jami qatorlar: {total} | Tahlil qilingan: {parsed}",
        "log_report_suspicious_count": "Shubhali IP manzillar: {count}",
        "log_report_none": "Ma'lum hujum signaturalariga mos keluvchi faoliyat topilmadi.",
        "log_report_top_header": "Eng shubhali IP manzillar (xavf balli bo'yicha):",
        "log_report_ip_line": "[!] {ip} — xavf balli: {score}, jami so'rov: {total}",
        "log_report_tip": "Tavsiya: yuqori xavf ballga ega IP manzillarni firewall/WAF darajasida bloklashni yoki fail2ban/nginx rate-limit qoidalarini kuchaytirishni ko'rib chiqing.",
        "sig_rate_burst": "Yuqori chastotali so'rovlar (mumkin bo'lgan brute-force/DoS)",
        "sig_error_bruteforce": "Ko'p 403/404 xatolar (mumkin bo'lgan directory/endpoint brute-force)",
    },
    "ru": {
        "choose_language": "Tilni tanlang / Выберите язык / Choose language:",
        "language_set": "Язык установлен на русский. Полное руководство: /help",
        "welcome": (
            "Добро пожаловать в SDeVPro Security Bot!\n\n"
            "Я провожу проверку безопасности вашей системы (веб-сайт, API или GitHub "
            "репозиторий) с помощью ИИ: нахожу уязвимости, объясняю как их исправить и, при "
            "желании, автоматически присылаю отчёт через заданный интервал времени.\n\n"
            "Перед началом введите свой AI (LLM) API токен: /setkey\n"
            "Полное руководство: /help"
        ),
        "help": (
            "SDeVPro — полное руководство\n\n"
            "1) СНАЧАЛА ВВЕДИТЕ AI ТОКЕН\n"
            "   /setkey — вводите свой токен OpenAI/Anthropic/Gemini/DeepSeek и т.д. Каждый "
            "пользователь работает со своим токеном, он хранится в зашифрованном виде и "
            "используется только для вас.\n"
            "   Где взять токен — /aitoken\n\n"
            "2) КОМАНДЫ ПРОВЕРКИ\n"
            "   /scan <адрес> — разовая полная проверка.\n"
            "     Например: /scan https://example.com\n"
            "     Или GitHub репозиторий: /scan https://github.com/foo/bar\n"
            "   /schedule <адрес> <интервал> — периодическая проверка (например, каждый час).\n"
            "     Например: /schedule https://example.com 1h\n"
            "   /unschedule <адрес> — отменить периодическую проверку.\n"
            "   /myschedules — список активных периодических проверок.\n"
            "   /report — получить последний отчёт снова (текст + PDF/TXT документ).\n\n"
            "3) АНАЛИЗ СЕРВЕРНЫХ ЛОГОВ\n"
            "   Отправьте боту файл .log или .txt — я найду подозрительные IP-адреса и "
            "попытки атак, дам полный отчёт (текст + документ для скачивания).\n\n"
            "4) GITHUB РЕПОЗИТОРИЙ\n"
            "   Публичные репозитории можно проверять напрямую через /scan.\n"
            "   Для приватного репозитория: /setgithubtoken <token> — как получить токен GitHub "
            "написано в команде /githubtoken.\n\n"
            "5) НАСТРОЙКИ\n"
            "   /language — сменить язык интерфейса (uz/ru/en).\n"
            "   /mysettings — текущие настройки (язык, статус токена).\n"
            "   /deletekey — удалить сохранённый AI токен.\n\n"
            "ВАЖНО: проверяйте только те системы, которые принадлежат вам или на проверку "
            "которых у вас есть письменное разрешение."
        ),
        "aitoken_help": (
            "Где получить AI (LLM) API токен:\n\n"
            "• Anthropic (Claude): console.anthropic.com -> Settings -> API Keys -> Create Key\n"
            "  Формат: /setkey anthropic/claude-sonnet-4-6 sk-ant-...\n\n"
            "• OpenAI (GPT): platform.openai.com/api-keys -> Create new secret key\n"
            "  Формат: /setkey openai/gpt-5.4 sk-...\n\n"
            "• Google Gemini: aistudio.google.com/app/apikey -> Create API key\n"
            "  Формат: /setkey gemini/gemini-3-pro-preview AIza...\n\n"
            "• DeepSeek: platform.deepseek.com/api_keys\n"
            "  Формат: /setkey deepseek/deepseek-v4-pro sk-...\n\n"
            "Ваш токен хранится в зашифрованном виде и используется только для ваших запросов."
        ),
        "setkey_usage": (
            "Использование: /setkey <provider>/<model> <api_token>\n"
            "Например: /setkey anthropic/claude-sonnet-4-6 sk-ant-xxxxxxxx\n"
            "Список провайдеров и где взять токен: /aitoken"
        ),
        "setkey_saved": "AI токен сохранён. Модель: {model}. Теперь можно начать проверку через /scan.",
        "deletekey_done": "Ваш AI токен удалён.",
        "deletekey_none": "У вас не было сохранённого AI токена.",
        "no_api_key": "У вас ещё не установлен AI токен. Сначала введите его через /setkey (инструкция: /aitoken).",
        "mysettings": "Язык: {language}\nAI модель: {model}\nGitHub токен: {github_token_status}",
        "github_token_set": "установлен",
        "github_token_unset": "не установлен",
        "setgithubtoken_usage": "Использование: /setgithubtoken <token>",
        "setgithubtoken_saved": "GitHub токен сохранён — теперь я могу проверять и приватные репозитории.",
        "githubtoken_help": (
            "Для проверки приватного GitHub репозитория нужен Personal Access Token:\n"
            "github.com -> Settings -> Developer settings -> Personal access tokens -> "
            "Fine-grained tokens -> создайте с правом только 'Contents: Read-only'.\n"
            "Затем: /setgithubtoken <token>"
        ),
        "consent_prompt": (
            "Перед началом проверки подтвердите:\n\n"
            "Я являюсь владельцем этого адреса (или системы), либо имею письменное разрешение "
            "на проведение проверки безопасности, и беру на себя полную ответственность за "
            "результаты этой проверки."
        ),
        "consent_button": "Да, у меня есть полномочия — начать",
        "consent_confirmed": "Подтверждено. Проверка начинается...",
        "scan_usage": "Использование: /scan <адрес>\nНапример: /scan https://example.com",
        "scan_started": "Проверка начата: {target}\n\nНачинается разведка (recon)...",
        "scan_progress": "Проверка продолжается: {target}\n\n{message}",
        "scan_done_preparing": "Проверка завершена. Готовится отчёт...",
        "schedule_usage": (
            "Использование: /schedule <адрес> <интервал>\n"
            "Например: /schedule https://example.com 1h\n"
            "Интервал: '30m', '1h', '2h30m' или целое число минут."
        ),
        "schedule_bad_interval": "Интервал некорректен или слишком короткий (минимум 5 минут).",
        "schedule_needs_consent": "Сначала выполните хотя бы одну проверку через /scan для подтверждения полномочий, затем повторите /schedule.",
        "schedule_set": "Периодическая проверка установлена: {target}\nОтчёт будет приходить каждые {minutes} минут.",
        "unschedule_usage": "Использование: /unschedule <адрес>",
        "unschedule_done": "Периодическая проверка отменена.",
        "unschedule_none": "Такая периодическая проверка не найдена.",
        "myschedules_none": "Нет активных периодических проверок.",
        "myschedules_header": "Активные периодические проверки:",
        "myschedules_item": "- {target} (каждые {minutes} мин.)",
        "report_none": "Пока нет сохранённого отчёта. Сначала выполните /scan.",
        "denied": "Извините, у вас нет доступа к этому боту.",
        "doc_only_log": "Принимаю только файлы серверных логов в формате .log или .txt.",
        "doc_too_big": "Файл слишком большой (не более 20МБ).",
        "doc_analyzing": "Анализирую файл логов...",
        "unexpected_error": "Произошла непредвиденная ошибка. Пожалуйста, попробуйте снова.",
        "scheduled_scan_failed": "Ошибка при периодической проверке ({target}). Повторная попытка позже.",
        "report_summary_title": "SDeVPro — Отчёт о проверке безопасности",
        "report_target": "Цель: {target}",
        "report_mode": "Режим: {mode} | {kind}",
        "report_kind_whitebox": "Проверка кода",
        "report_kind_github": "GitHub репозиторий",
        "report_kind_blackbox": "Внешняя (blackbox)",
        "report_started": "Начато: {time}",
        "report_finished": "Завершено: {time}",
        "report_findings_summary": "Сводка по найденным проблемам:",
        "report_no_findings": "  Проблем не обнаружено.",
        "report_error": "[!] Ошибка во время проверки: {error}",
        "report_ai_summary": "Заключение ИИ:",
        "report_defense_title": "SDeVPro — Общие рекомендации по защите",
        "finding_category": "Категория: {value}",
        "finding_location": "Расположение: {value}",
        "finding_description": "Описание: {value}",
        "finding_attack_vector": "Вектор атаки: {value}",
        "finding_remediation": "Исправление: {value}",
        "pdf_caption": "Полный отчёт в PDF",
        "txt_caption": "Полный текстовый отчёт (.txt)",
        "no_git": "Git не установлен на сервере — проверка GitHub репозиториев недоступна. Сообщите администратору.",
        "github_clone_failed": "Не удалось загрузить репозиторий (неверный адрес, приватный репозиторий или нужен токен). Для приватного репозитория: /githubtoken",
        "progress_recon_started": "Разведка начата: {target}",
        "progress_recon_done": "Разведка завершена: найдено {ports} открытых портов, {tech} технологий.",
        "progress_codescan_started": "Проверка исходного кода (секреты, опасные шаблоны)...",
        "progress_codescan_done": "Проверка кода завершена: проверено файлов — {files}.",
        "progress_webprobe_started": "Проверка веб-уязвимостей (XSS, SQLi, CORS, открытые файлы)...",
        "progress_webprobe_done": "Проверка завершена: найдено {count}.",
        "progress_ai_analyzing": "ИИ-аналитик оценивает результаты...",
        "progress_ai_done": "Анализ ИИ завершён.",
        "progress_github_cloning": "Загружается GitHub репозиторий: {target}",
        "progress_github_cloned": "Репозиторий загружен, проверяется код...",
        "ai_failed_fallback": "Анализ ИИ не удался; ниже приведены необработанные (без ИИ) результаты.",
        "log_report_title": "SDeVPro — Анализ атак по серверным логам",
        "log_report_totals": "Всего строк: {total} | Проанализировано: {parsed}",
        "log_report_suspicious_count": "Подозрительные IP-адреса: {count}",
        "log_report_none": "Активность, соответствующая известным сигнатурам атак, не обнаружена.",
        "log_report_top_header": "Самые подозрительные IP-адреса (по уровню риска):",
        "log_report_ip_line": "[!] {ip} — уровень риска: {score}, всего запросов: {total}",
        "log_report_tip": "Рекомендация: рассмотрите блокировку IP с высоким риском на уровне firewall/WAF или ужесточение правил fail2ban/nginx rate-limit.",
        "sig_rate_burst": "Высокая частота запросов (возможен brute-force/DoS)",
        "sig_error_bruteforce": "Много ошибок 403/404 (возможен перебор директорий/эндпоинтов)",
    },
    "en": {
        "choose_language": "Tilni tanlang / Выберите язык / Choose language:",
        "language_set": "Language set to English. Full guide: /help",
        "welcome": (
            "Welcome to the SDeVPro Security Bot!\n\n"
            "I run an AI-powered security assessment of your system (website, API, or GitHub "
            "repository): I find vulnerabilities, explain how to fix them, and, if you'd like, "
            "send you an automatic report on a schedule.\n\n"
            "Before you start, enter your own AI (LLM) API token: /setkey\n"
            "Full guide: /help"
        ),
        "help": (
            "SDeVPro — full guide\n\n"
            "1) SET YOUR AI TOKEN FIRST\n"
            "   /setkey — enter your own OpenAI/Anthropic/Gemini/DeepSeek etc. API token. Every "
            "user works with their own token; it is stored encrypted and used only for you.\n"
            "   Where to get a token — /aitoken\n\n"
            "2) SCAN COMMANDS\n"
            "   /scan <target> — one-off full assessment.\n"
            "     Example: /scan https://example.com\n"
            "     Or a GitHub repo: /scan https://github.com/foo/bar\n"
            "   /schedule <target> <interval> — recurring scan (e.g. hourly).\n"
            "     Example: /schedule https://example.com 1h\n"
            "   /unschedule <target> — cancel a recurring scan.\n"
            "   /myschedules — list active recurring scans.\n"
            "   /report — resend the last report (text + PDF/TXT document).\n\n"
            "3) SERVER LOG ANALYSIS\n"
            "   Send the bot a .log or .txt file — I'll flag suspicious IPs and attack attempts "
            "and give you a full report (text + downloadable document).\n\n"
            "4) GITHUB REPOSITORY\n"
            "   Public repos can be scanned directly via /scan.\n"
            "   For a private repo: /setgithubtoken <token> — see /githubtoken for how to get one.\n\n"
            "5) SETTINGS\n"
            "   /language — change interface language (uz/ru/en).\n"
            "   /mysettings — your current settings (language, token status).\n"
            "   /deletekey — remove your stored AI token.\n\n"
            "IMPORTANT: only scan systems you own or have written authorization to test."
        ),
        "aitoken_help": (
            "Where to get an AI (LLM) API token:\n\n"
            "• Anthropic (Claude): console.anthropic.com -> Settings -> API Keys -> Create Key\n"
            "  Format: /setkey anthropic/claude-sonnet-4-6 sk-ant-...\n\n"
            "• OpenAI (GPT): platform.openai.com/api-keys -> Create new secret key\n"
            "  Format: /setkey openai/gpt-5.4 sk-...\n\n"
            "• Google Gemini: aistudio.google.com/app/apikey -> Create API key\n"
            "  Format: /setkey gemini/gemini-3-pro-preview AIza...\n\n"
            "• DeepSeek: platform.deepseek.com/api_keys\n"
            "  Format: /setkey deepseek/deepseek-v4-pro sk-...\n\n"
            "Your token is stored encrypted and used only for your own requests — nobody else "
            "can see it."
        ),
        "setkey_usage": (
            "Usage: /setkey <provider>/<model> <api_token>\n"
            "Example: /setkey anthropic/claude-sonnet-4-6 sk-ant-xxxxxxxx\n"
            "Provider list and where to get a token: /aitoken"
        ),
        "setkey_saved": "AI token saved. Model: {model}. You can now start a scan with /scan.",
        "deletekey_done": "Your AI token has been deleted.",
        "deletekey_none": "You had no stored AI token.",
        "no_api_key": "You haven't set an AI token yet. Set one first with /setkey (guide: /aitoken).",
        "mysettings": "Language: {language}\nAI model: {model}\nGitHub token: {github_token_status}",
        "github_token_set": "set",
        "github_token_unset": "not set",
        "setgithubtoken_usage": "Usage: /setgithubtoken <token>",
        "setgithubtoken_saved": "GitHub token saved — I can now also scan private repositories.",
        "githubtoken_help": (
            "To scan a private GitHub repository you need a Personal Access Token:\n"
            "github.com -> Settings -> Developer settings -> Personal access tokens -> "
            "Fine-grained tokens -> create one with only 'Contents: Read-only' permission.\n"
            "Then: /setgithubtoken <token>"
        ),
        "consent_prompt": (
            "Please confirm before the scan starts:\n\n"
            "I own this target (or system), or I have written authorization to run a security "
            "assessment against it, and I take full responsibility for the results of this scan."
        ),
        "consent_button": "Yes, I'm authorized — start",
        "consent_confirmed": "Confirmed. Scan starting...",
        "scan_usage": "Usage: /scan <target>\nExample: /scan https://example.com",
        "scan_started": "Scan started: {target}\n\nRecon starting...",
        "scan_progress": "Scan in progress: {target}\n\n{message}",
        "scan_done_preparing": "Scan finished. Preparing the report...",
        "schedule_usage": (
            "Usage: /schedule <target> <interval>\n"
            "Example: /schedule https://example.com 1h\n"
            "Interval: '30m', '1h', '2h30m', or a plain integer number of minutes."
        ),
        "schedule_bad_interval": "Invalid or too short an interval (minimum 5 minutes).",
        "schedule_needs_consent": "Run /scan at least once first to confirm authorization, then send /schedule again.",
        "schedule_set": "Recurring scan set: {target}\nA report will be sent automatically every {minutes} minutes.",
        "unschedule_usage": "Usage: /unschedule <target>",
        "unschedule_done": "Recurring scan cancelled.",
        "unschedule_none": "No such recurring scan found.",
        "myschedules_none": "No active recurring scans.",
        "myschedules_header": "Active recurring scans:",
        "myschedules_item": "- {target} (every {minutes} min)",
        "report_none": "No saved report yet. Run /scan first.",
        "denied": "Sorry, you don't have access to this bot.",
        "doc_only_log": "I only accept server log files in .log or .txt format.",
        "doc_too_big": "File is too large (max 20MB).",
        "doc_analyzing": "Analyzing the log file...",
        "unexpected_error": "An unexpected error occurred. Please try again.",
        "scheduled_scan_failed": "Recurring scan failed ({target}). Will retry next cycle.",
        "report_summary_title": "SDeVPro — Security Scan Report",
        "report_target": "Target: {target}",
        "report_mode": "Mode: {mode} | {kind}",
        "report_kind_whitebox": "Code scan",
        "report_kind_github": "GitHub repository",
        "report_kind_blackbox": "External (blackbox)",
        "report_started": "Started: {time}",
        "report_finished": "Finished: {time}",
        "report_findings_summary": "Findings summary:",
        "report_no_findings": "  No findings.",
        "report_error": "[!] Error during scan: {error}",
        "report_ai_summary": "AI summary:",
        "report_defense_title": "SDeVPro — General Defense Recommendations",
        "finding_category": "Category: {value}",
        "finding_location": "Location: {value}",
        "finding_description": "Description: {value}",
        "finding_attack_vector": "Attack vector: {value}",
        "finding_remediation": "Remediation: {value}",
        "pdf_caption": "Full PDF report",
        "txt_caption": "Full text report (.txt)",
        "no_git": "Git is not installed on the server — GitHub repository scanning is unavailable. Contact the administrator.",
        "github_clone_failed": "Could not fetch the repository (wrong URL, private repo, or a token is needed). For a private repo: /githubtoken",
        "progress_recon_started": "Recon started: {target}",
        "progress_recon_done": "Recon done: {ports} open ports, {tech} technologies detected.",
        "progress_codescan_started": "Scanning source code (secrets, dangerous patterns)...",
        "progress_codescan_done": "Code scan done: {files} files scanned.",
        "progress_webprobe_started": "Checking web vulnerabilities (XSS, SQLi, CORS, exposed files)...",
        "progress_webprobe_done": "Web probe done: {count} findings.",
        "progress_ai_analyzing": "AI analyst is evaluating the findings...",
        "progress_ai_done": "AI analysis done.",
        "progress_github_cloning": "Fetching GitHub repository: {target}",
        "progress_github_cloned": "Repository fetched, scanning code...",
        "ai_failed_fallback": "AI analysis failed; the raw (un-triaged) findings are shown below.",
        "log_report_title": "SDeVPro — Server Log Attack Analysis",
        "log_report_totals": "Total lines: {total} | Parsed: {parsed}",
        "log_report_suspicious_count": "Suspicious IP addresses: {count}",
        "log_report_none": "No activity matching known attack signatures was found.",
        "log_report_top_header": "Most suspicious IP addresses (by risk score):",
        "log_report_ip_line": "[!] {ip} — risk score: {score}, total requests: {total}",
        "log_report_tip": "Tip: consider blocking high-risk IPs at the firewall/WAF level, or tightening fail2ban/nginx rate-limit rules.",
        "sig_rate_burst": "High request rate (possible brute-force/DoS)",
        "sig_error_bruteforce": "Many 403/404 errors (possible directory/endpoint brute-forcing)",
    },
}


def t(lang: str | None, key: str, **kwargs: object) -> str:
    lang = lang if lang in _TR else DEFAULT_LANGUAGE
    template = _TR.get(lang, {}).get(key) or _TR[DEFAULT_LANGUAGE].get(key) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template


def severity_label(lang: str | None, severity: str) -> str:
    lang = lang if lang in SEVERITY_LABELS else DEFAULT_LANGUAGE
    return SEVERITY_LABELS.get(lang, {}).get(severity, severity.upper())
