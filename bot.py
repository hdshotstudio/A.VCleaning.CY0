
# bot.py — AV Cleaning CY (Design v2, no time selection)
import logging
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
import db

# ========== CONFIG ==========
BOT_TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"  # ← вставь токен BotFather
ADMIN_IDS = [5570877977, 1214168275]   # двойная админка
COMPANY_NAME = "AV Cleaning CY"
INSTAGRAM_URL = "https://www.instagram.com/a.vcleaning.cy/"
CONTACT_USERNAME = "adrian_handsome"
SIGNATURE = "💎 AV Cleaning CY — чистота, которой можно доверять"
LOGO_PATH = "assets/logo.jpg"
# ============================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
(SERVICE, DATE, ADDRESS, PHONE, CONFIRM) = range(5)

SERVICES = [
    ("🏠 Генеральная уборка", "Глубокая очистка всех помещений, техника и труднодоступные зоны."),
    ("🧹 Поддерживающая уборка", "Быстрая уборка для ежедневной свежести и уюта."),
    ("🏢 Уборка офиса", "Чистое рабочее пространство для команды и клиентов."),
    ("🪣 Послестроительная уборка", "Удаляем строительную пыль и следы ремонта.")
]

def gen_dates(days=14):
    base = datetime.now().date()
    return [(base + timedelta(days=i)).isoformat() for i in range(0, days)]

def booking_text(b: dict) -> str:
    user = b.get('username') or str(b['user_id'])
    if isinstance(user, str) and user and not user.startswith("@"):
        user = f"@{user}"
    lines = [
        "💎 Новая заявка от клиента!",
        "──────────────────────────────",
        f"👤 Имя: {user}",
        f"🧽 Услуга: {b['service']}",
        f"📅 Дата: {b['date']}",
        f"📍 Адрес: {b.get('address')}",
        f"📞 Телефон: {b.get('phone')}",
        "──────────────────────────────",
        SIGNATURE
    ]
    return "\n".join(lines)

def booking_text_compact(b: dict) -> str:
    return (f"🧾 Запись #{b['id']}\n"
            f"Услуга: {b['service']}\n"
            f"Дата: {b['date']}\n"
            f"Адрес: {b.get('address')}\n"
            f"Телефон: {b.get('phone')}\n"
            f"Статус: {b.get('status')}\n\n{SIGNATURE}")

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧽 Записаться на уборку", callback_data="book")],
        [InlineKeyboardButton("🧺 Наши услуги", callback_data="services")],
        [InlineKeyboardButton("💬 Связаться с администратором", url=f"https://t.me/{CONTACT_USERNAME}")],
        [InlineKeyboardButton("📸 Instagram", url=INSTAGRAM_URL)]
    ])

def services_menu_kb():
    rows = []
    for i, (title, _desc) in enumerate(SERVICES):
        rows.append([InlineKeyboardButton(title, callback_data=f"svcinfo|{i}")])
    rows.append([InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu")])
    return InlineKeyboardMarkup(rows)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Try send logo
    try:
        with open(LOGO_PATH, "rb") as f:
            await (update.message.reply_photo if update.message else update.callback_query.message.reply_photo)(
                photo=f,
                caption=(
                    "👋 Добро пожаловать в <b>AV Cleaning CY</b>\n"
                    "Премиальный клининг на Кипре 🏝\n\n"
                    "Выберите действие ниже 👇"
                ),
                parse_mode="HTML",
                reply_markup=main_menu_kb()
            )
            return
    except Exception as e:
        logger.warning("Не удалось отправить логотип: %s", e)
    # Fallback text
    target = update.message or update.callback_query.message
    await target.reply_html(
        "👋 Добро пожаловать в <b>AV Cleaning CY</b>\n"
        "Премиальный клининг на Кипре 🏝\n\n"
        "Выберите действие ниже 👇",
        reply_markup=main_menu_kb()
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start — меню\n"
        "/book — записаться\n"
        "/mybookings — мои записи\n"
        "/bookings — все записи (админ)\n"
        "/help — помощь"
    )

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_reply_markup(reply_markup=main_menu_kb())

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    text = "🧺 <b>Наши услуги</b>\n\n" + "\n\n".join([
        f"{title}\n— {desc}" for title, desc in SERVICES
    ])
    await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=services_menu_kb())

async def service_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, idx = update.callback_query.data.split("|")
    idx = int(idx)
    title, desc = SERVICES[idx]
    text = f"{title}\n\n{desc}\n\nНажмите «Записаться», чтобы оставить заявку."
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧽 Записаться", callback_data="book")],
        [InlineKeyboardButton("⬅️ Назад к услугам", callback_data="services")]
    ])
    await update.callback_query.message.edit_text(text, reply_markup=kb)

# Booking flow
async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        send = update.callback_query.message
    else:
        send = update.message
    kb = [[InlineKeyboardButton(title, callback_data=f"service|{i}")] for i,(title,_d) in enumerate(SERVICES)]
    await send.reply_text("Выберите услугу:", reply_markup=InlineKeyboardMarkup(kb))
    return SERVICE

async def service_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, idx = update.callback_query.data.split("|")
    idx = int(idx)
    context.user_data['service'] = SERVICES[idx][0]

    dates = gen_dates(14)
    kb, row = [], []
    for d in dates:
        row.append(InlineKeyboardButton(d, callback_data=f"date|{d}"))
        if len(row) == 3:
            kb.append(row); row = []
    if row: kb.append(row)
    await update.callback_query.message.reply_text("📅 Выберите дату (время согласуем вручную):", reply_markup=InlineKeyboardMarkup(kb))
    return DATE

async def date_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, date = update.callback_query.data.split("|")
    context.user_data['date'] = date
    await update.callback_query.message.reply_text("📍 Напишите адрес (улица, дом, этаж/кв):")
    return ADDRESS

async def address_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['address'] = update.message.text.strip()
    kb = ReplyKeyboardMarkup([[KeyboardButton("Отправить контакт", request_contact=True)],
                              ["Ввести номер вручную"]],
                             resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("☎️ Отправьте контакт или введите номер телефона:", reply_markup=kb)
    return PHONE

async def phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text.strip()
    context.user_data['phone'] = phone

    summary = (f"Проверьте запись:\n\n"
               f"{context.user_data['service']}\n"
               f"📅 {context.user_data['date']}\n"
               f"📍 {context.user_data['address']}\n"
               f"☎️ {context.user_data['phone']}\n\n{SIGNATURE}")
    kb = [[InlineKeyboardButton("✅ Подтвердить", callback_data="confirm|yes"),
           InlineKeyboardButton("❌ Отменить", callback_data="confirm|no")]]
    await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(kb))
    return CONFIRM

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, choice = update.callback_query.data.split("|")
    if choice == "no":
        await update.callback_query.message.reply_text("Запись отменена. Для новой записи используйте /book")
        return ConversationHandler.END

    booking = {
        'user_id': update.effective_user.id,
        'username': update.effective_user.username or update.effective_user.full_name,
        'service': context.user_data['service'],
        'date': context.user_data['date'],
        'address': context.user_data['address'],
        'phone': context.user_data['phone'],
    }
    bid = await db.add_booking(booking)
    await update.callback_query.message.reply_text(
        f"✅ Готово — ваша запись #{bid} создана. Мы свяжемся с вами для согласования времени.\n\n{SIGNATURE}"
    )

    b = await db.get_booking(bid)
    text = booking_text(b)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Принять", callback_data=f"admin|accept|{bid}"),
         InlineKeyboardButton("❌ Отменить", callback_data=f"admin|cancel|{bid}")],
        [InlineKeyboardButton("📞 Связаться с клиентом", callback_data=f"admin|contact|{bid}")]
    ])
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, text, reply_markup=kb)
        except Exception as e:
            logger.exception("Не удалось отправить админу: %s", e)

    return ConversationHandler.END

# Admin actions
async def admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, action, bid = update.callback_query.data.split("|")
    bid = int(bid)

    if action == "accept":
        await db.update_status(bid, "accepted")
        b = await db.get_booking(bid)
        await update.callback_query.message.edit_text("✅ Заявка подтверждена\n\n" + booking_text_compact(b))
        try:
            await context.bot.send_message(b['user_id'], f"✅ Ваша запись #{bid} подтверждена. Время согласует администратор.\n\n{SIGNATURE}")
        except Exception:
            pass

    elif action == "cancel":
        await db.update_status(bid, "cancelled")
        b = await db.get_booking(bid)
        await update.callback_query.message.edit_text("❌ Заявка отменена\n\n" + booking_text_compact(b))
        try:
            await context.bot.send_message(b['user_id'], f"❌ Ваша запись #{bid} отменена. Для новой записи используйте /book\n\n{SIGNATURE}")
        except Exception:
            pass

    elif action == "contact":
        b = await db.get_booking(bid)
        await update.callback_query.message.reply_text(
            f"📞 Контакт клиента\n👤 @{b.get('username')}\n☎️ {b.get('phone')}\n\n{SIGNATURE}"
        )

# Lists
async def mybookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = await db.user_bookings(user_id)
    if not rows:
        await update.effective_message.reply_text("У вас нет записей.\n\n" + SIGNATURE)
        return
    for r in rows:
        await update.effective_message.reply_text(booking_text_compact(r))

async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Доступ только для админов.")
        return
    rows = await db.list_bookings()
    if not rows:
        await update.message.reply_text("Нет записей.")
        return
    for r in rows:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Принять", callback_data=f"admin|accept|{r['id']}"),
             InlineKeyboardButton("❌ Отменить", callback_data=f"admin|cancel|{r['id']}")]
        ])
        await update.message.reply_text(booking_text_compact(r), reply_markup=kb)

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция прервана.")
    return ConversationHandler.END

def main():
    import asyncio
    asyncio.run(db.init_db())

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler('book', book_start), CallbackQueryHandler(book_start, pattern="^book$")],
        states={
            SERVICE: [CallbackQueryHandler(service_chosen, pattern="^service\|")],
            DATE: [CallbackQueryHandler(date_chosen, pattern="^date\|")],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_received)],
            PHONE: [MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, phone_received)],
            CONFIRM: [CallbackQueryHandler(confirm_booking, pattern="^confirm\|")]
        },
        fallbacks=[CommandHandler('cancel', cancel_conv)]
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(show_menu, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(show_services, pattern="^services$"))
    app.add_handler(CallbackQueryHandler(service_info, pattern="^svcinfo\|"))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(CommandHandler('mybookings', mybookings))
    app.add_handler(CommandHandler('bookings', admin_list))
    app.add_handler(CallbackQueryHandler(admin_button, pattern="^admin\|"))

    app.run_polling(close_loop=False)

if __name__ == '__main__':
    main()
