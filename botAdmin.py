import os
import json
import random
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    PicklePersistence,
    filters,
)

DATA_FILE = "recipes.json"
PERSISTENCE_FILE = "bot_data_persistence.pkl"

# ВАЖНО: поставь сюда свой user_id (можно узнать командой /myid)
ADMIN_ID = 1224613559

MAIN_KB = ReplyKeyboardMarkup(
    [["📚 Каталог", "🍲 Случайный рецепт", "🔎 Поиск"],
     ["➕ Добавить рецепт", "⭐ Избранное"]],
    resize_keyboard=True,
)

ADD_TITLE, ADD_INGR, ADD_STEPS, ADD_PHOTO = range(4)

# callback_data (короткие префиксы)
CB_FAV_ADD = "fa:"          # fa:<rid>
CB_FAV_DEL = "fd:"          # fd:<rid>

CB_CAT_PAGE = "cp:"         # cp:<page>
CB_CAT_SHOW = "cs:"         # cs:<rid>

CB_FAV_SHOW_PAGE = "fp:"    # fp:<page>
CB_FAV_SHOW_ITEM = "fs:"    # fs:<rid>

CB_DEL_ASK = "da:"          # da:<rid> запрос подтверждения
CB_DEL_OK = "do:"           # do:<rid> подтверждение
CB_DEL_NO = "dn:"           # dn:<rid> отмена

CAT_PAGE_SIZE = 5
FAV_PAGE_SIZE = 5


@dataclass
class Recipe:
    id: int
    title: str
    ingredients: List[str]
    steps: str
    photo_file_id: Optional[str] = None


def load_recipes() -> List[Recipe]:
    if not os.path.exists(DATA_FILE):
        return [
            Recipe(
                id=1,
                title="Омлет",
                ingredients=["Яйца (2 шт.)", "Молоко (50 мл)", "Соль", "Масло"],
                steps="Взбей яйца с молоком и солью. Обжарь на сковороде 3–5 минут.",
            ),
            Recipe(
                id=2,
                title="Овсянка",
                ingredients=["Овсяные хлопья (50 г)", "Вода/молоко (200 мл)", "Соль/сахар"],
                steps="Доведи жидкость до кипения, всыпь хлопья и вари 3–5 минут.",
            ),
            Recipe(
                id=3,
                title="Гречка",
                ingredients=["Гречка (1 стакан)", "Вода (2 стакана)", "Соль", "Масло (по желанию)"],
                steps="Промой гречку. Залей водой, посоли, доведи до кипения и вари под крышкой 15–20 минут.",
            ),
            Recipe(
                id=4,
                title="Макароны с сыром",
                ingredients=["Макароны (150 г)", "Сыр (50–80 г)", "Соль", "Масло (по желанию)"],
                steps="Отвари макароны в подсоленной воде. Слей воду, добавь сыр, перемешай до расплавления.",
            ),
            Recipe(
                id=5,
                title="Салат из огурцов и помидоров",
                ingredients=["Огурец (1–2 шт.)", "Помидор (1–2 шт.)", "Лук (по желанию)", "Соль", "Масло/сметана"],
                steps="Нарежь овощи, посоли, заправь маслом или сметаной, перемешай.",
            ),
            Recipe(
                id=6,
                title="Картофельное пюре",
                ingredients=["Картофель (500 г)", "Молоко (100 мл)", "Масло (30 г)", "Соль"],
                steps="Отвари картофель до мягкости, слей воду. Разомни, добавь масло и горячее молоко, посоли.",
            ),
            Recipe(
                id=7,
                title="Курица на сковороде",
                ingredients=["Куриное филе (300 г)", "Соль", "Перец", "Масло"],
                steps="Нарежь филе, посоли/поперчи. Обжарь 8–12 минут до готовности.",
            ),
            Recipe(
                id=8,
                title="Рис с овощами",
                ingredients=["Рис (1 стакан)", "Овощи замороженные (200 г)", "Соль", "Масло/соевый соус (по желанию)"],
                steps="Отвари рис. Прогрей овощи 5–7 минут, смешай, посоли.",
            ),
            Recipe(
                id=9,
                title="Сырники (простые)",
                ingredients=["Творог (300 г)", "Яйцо (1 шт.)", "Сахар (1–2 ст. л.)", "Мука (3–4 ст. л.)", "Масло"],
                steps="Смешай всё, сформируй сырники и обжарь по 2–3 минуты с каждой стороны.",
            ),
            Recipe(
                id=10,
                title="Блины (базовые)",
                ingredients=["Молоко (500 мл)", "Яйца (2 шт.)", "Мука (200–250 г)", "Сахар (1 ст. л.)", "Соль", "Масло"],
                steps="Смешай, добавь муку, жарь тонкие блины на смазанной сковороде.",
            ),
        ]

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    recipes: List[Recipe] = []
    for item in raw:
        recipes.append(
            Recipe(
                id=int(item.get("id", 0)),
                title=item.get("title", ""),
                ingredients=item.get("ingredients", []),
                steps=item.get("steps", ""),
                photo_file_id=item.get("photo_file_id"),
            )
        )

    # совместимость со старым файлом без id
    if any(r.id == 0 for r in recipes):
        for i, r in enumerate(recipes, start=1):
            r.id = i
        save_recipes(recipes)

    return recipes


def save_recipes(recipes: List[Recipe]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in recipes], f, ensure_ascii=False, indent=2)


def next_recipe_id(recipes: List[Recipe]) -> int:
    return max((r.id for r in recipes), default=0) + 1


def ensure_favs(context: ContextTypes.DEFAULT_TYPE) -> List[int]:
    favs = context.user_data.get("favs")
    if not isinstance(favs, list):
        context.user_data["favs"] = []
    return context.user_data["favs"]


def find_recipe_by_id(recipes: List[Recipe], rid: int) -> Optional[Recipe]:
    for r in recipes:
        if r.id == rid:
            return r
    return None


def format_recipe(r: Recipe) -> str:
    ingr = "\n".join(f"• {x}" for x in r.ingredients)
    return f"🍽 {r.title}\n\n🧾 Ингредиенты:\n{ingr}\n\n👩‍🍳 Шаги:\n{r.steps}"


def paginate(items: List[Recipe], page: int, page_size: int) -> Tuple[List[Recipe], int, int]:
    if page < 1:
        page = 1
    total_pages = max(1, (len(items) + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total_pages, page


def recipe_actions_keyboard(recipe_id: int, is_fav: bool, is_admin: bool) -> InlineKeyboardMarkup:
    fav_btn = (
        InlineKeyboardButton("❌ Убрать из избранного", callback_data=f"{CB_FAV_DEL}{recipe_id}")
        if is_fav
        else InlineKeyboardButton("⭐ В избранное", callback_data=f"{CB_FAV_ADD}{recipe_id}")
    )

    rows = [[fav_btn]]

    if is_admin:
        rows.append([InlineKeyboardButton("🗑 Удалить рецепт", callback_data=f"{CB_DEL_ASK}{recipe_id}")])

    rows.append([
        InlineKeyboardButton("📚 Каталог", callback_data=f"{CB_CAT_PAGE}1"),
        InlineKeyboardButton("⭐ Избранное", callback_data=f"{CB_FAV_SHOW_PAGE}1"),
    ])
    return InlineKeyboardMarkup(rows)


def catalog_keyboard(recipes: List[Recipe], page: int) -> InlineKeyboardMarkup:
    page_items, total_pages, page = paginate(recipes, page, CAT_PAGE_SIZE)

    rows = []
    for r in page_items:
        rows.append([InlineKeyboardButton(r.title, callback_data=f"{CB_CAT_SHOW}{r.id}")])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{CB_CAT_PAGE}{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{CB_CAT_PAGE}{page+1}"))
    rows.append(nav)

    return InlineKeyboardMarkup(rows)


def favs_keyboard(recipes: List[Recipe], fav_ids: List[int], page: int) -> InlineKeyboardMarkup:
    fav_set = set(fav_ids)
    fav_recipes = [r for r in recipes if r.id in fav_set]

    page_items, total_pages, page = paginate(fav_recipes, page, FAV_PAGE_SIZE)

    rows = []
    for r in page_items:
        rows.append([InlineKeyboardButton(r.title, callback_data=f"{CB_FAV_SHOW_ITEM}{r.id}")])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{CB_FAV_SHOW_PAGE}{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{CB_FAV_SHOW_PAGE}{page+1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton("📚 Каталог", callback_data=f"{CB_CAT_PAGE}1")])
    return InlineKeyboardMarkup(rows)


async def send_recipe_message(chat_id: int, context: ContextTypes.DEFAULT_TYPE, r: Recipe, is_admin: bool) -> None:
    favs = ensure_favs(context)
    kb = recipe_actions_keyboard(r.id, is_fav=(r.id in favs), is_admin=is_admin)
    text = format_recipe(r)

    # Фото отдельно, текст отдельно (из-за лимита caption у медиа) [web:9]
    if r.photo_file_id:
        await context.bot.send_photo(chat_id=chat_id, photo=r.photo_file_id)
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)


# ---- handlers ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.application.bot_data["recipes"] = load_recipes()
    ensure_favs(context)
    await update.message.reply_text("Привет! Выбирай действие 👇", reply_markup=MAIN_KB)


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Ваш user_id: {update.effective_user.id}")


async def random_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    recipes: List[Recipe] = context.application.bot_data.get("recipes", load_recipes())
    r = random.choice(recipes)
    await send_recipe_message(update.effective_chat.id, context, r, is_admin=(update.effective_user.id == ADMIN_ID))
    await update.message.reply_text("Что дальше?", reply_markup=MAIN_KB)


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    recipes: List[Recipe] = context.application.bot_data.get("recipes", load_recipes())
    await update.message.reply_text(
        "📚 Каталог рецептов: выбери рецепт или листай страницы.",
        reply_markup=catalog_keyboard(recipes, page=1),
    )


async def show_favs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    recipes: List[Recipe] = context.application.bot_data.get("recipes", load_recipes())
    favs = ensure_favs(context)
    if not favs:
        await update.message.reply_text("Избранное пустое. Добавь рецепт кнопкой ⭐.", reply_markup=MAIN_KB)
        return
    await update.message.reply_text("⭐ Избранное:", reply_markup=favs_keyboard(recipes, favs, page=1))


async def search_hint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Напиши запрос: название или ингредиент (например: 'курица' или 'омлет').",
        reply_markup=ReplyKeyboardRemove(),
    )


async def search_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = (update.message.text or "").strip().lower()
    recipes: List[Recipe] = context.application.bot_data.get("recipes", load_recipes())

    hits: List[Recipe] = []
    for r in recipes:
        if q in r.title.lower() or any(q in ing.lower() for ing in r.ingredients):
            hits.append(r)

    if not hits:
        await update.message.reply_text("Ничего не нашлось. Попробуй другой запрос.", reply_markup=MAIN_KB)
        return

    await send_recipe_message(update.effective_chat.id, context, hits[0], is_admin=(update.effective_user.id == ADMIN_ID))
    await update.message.reply_text(f"Нашлось: {len(hits)}. Открой 📚 Каталог, чтобы выбрать другие.", reply_markup=MAIN_KB)


# ---- add recipe conversation ----
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Название рецепта?", reply_markup=ReplyKeyboardRemove())
    return ADD_TITLE


async def add_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_recipe_title"] = (update.message.text or "").strip()
    await update.message.reply_text("Ингредиенты через запятую:")
    return ADD_INGR


async def add_ingredients(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    context.user_data["new_recipe_ingredients"] = [x.strip() for x in text.split(",") if x.strip()]
    await update.message.reply_text("Шаги приготовления (текстом):")
    return ADD_STEPS


async def add_steps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_recipe_steps"] = (update.message.text or "").strip()
    await update.message.reply_text("Пришли фото блюда (или напиши '-' чтобы пропустить):")
    return ADD_PHOTO


async def add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = context.user_data.get("new_recipe_title", "").strip()
    ingredients = context.user_data.get("new_recipe_ingredients", [])
    steps = context.user_data.get("new_recipe_steps", "").strip()

    if not title or not ingredients or not steps:
        await update.message.reply_text("Не хватает данных. Начни заново: /start", reply_markup=MAIN_KB)
        return ConversationHandler.END

    photo_file_id = None
    if update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
    else:
        text = (update.message.text or "").strip()
        if text != "-":
            await update.message.reply_text("Пришли именно фото, или '-' чтобы пропустить.")
            return ADD_PHOTO

    recipes: List[Recipe] = context.application.bot_data.get("recipes", load_recipes())
    rid = next_recipe_id(recipes)
    recipes.append(Recipe(id=rid, title=title, ingredients=ingredients, steps=steps, photo_file_id=photo_file_id))
    context.application.bot_data["recipes"] = recipes
    save_recipes(recipes)

    await update.message.reply_text("Рецепт добавлен ✅", reply_markup=MAIN_KB)
    return ConversationHandler.END


async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.", reply_markup=MAIN_KB)
    return ConversationHandler.END


# ---- callbacks ----
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    chat_id = query.message.chat_id if query.message else None
    if chat_id is None:
        return

    recipes: List[Recipe] = context.application.bot_data.get("recipes", load_recipes())
    favs = ensure_favs(context)

    if data == "noop":
        return

    # ---- Каталог ----
    if data.startswith(CB_CAT_PAGE):
        page = int(data.replace(CB_CAT_PAGE, "") or "1")
        await query.edit_message_text(
            text="📚 Каталог рецептов: выбери рецепт или листай страницы.",
            reply_markup=catalog_keyboard(recipes, page=page),
        )
        return

    if data.startswith(CB_CAT_SHOW):
        rid = int(data.replace(CB_CAT_SHOW, ""))
        r = find_recipe_by_id(recipes, rid)
        if r:
            await send_recipe_message(chat_id, context, r, is_admin=(query.from_user.id == ADMIN_ID))
        else:
            await context.bot.send_message(chat_id=chat_id, text="Рецепт не найден (возможно удалён).")
        return

    # ---- Избранное ----
    if data.startswith(CB_FAV_SHOW_PAGE):
        page = int(data.replace(CB_FAV_SHOW_PAGE, "") or "1")
        if not favs:
            await context.bot.send_message(chat_id=chat_id, text="Избранное пустое.")
            return
        await query.edit_message_text(text="⭐ Избранное:", reply_markup=favs_keyboard(recipes, favs, page=page))
        return

    if data.startswith(CB_FAV_SHOW_ITEM):
        rid = int(data.replace(CB_FAV_SHOW_ITEM, ""))
        r = find_recipe_by_id(recipes, rid)
        if r:
            await send_recipe_message(chat_id, context, r, is_admin=(query.from_user.id == ADMIN_ID))
        else:
            await context.bot.send_message(chat_id=chat_id, text="Рецепт не найден (возможно удалён).")
        return

    # ---- Добавить/убрать избранное ----
    if data.startswith(CB_FAV_ADD):
        rid = int(data.replace(CB_FAV_ADD, ""))
        if rid not in favs:
            favs.append(rid)
        await context.bot.send_message(chat_id=chat_id, text="Добавлено в избранное ⭐")
        return

    if data.startswith(CB_FAV_DEL):
        rid = int(data.replace(CB_FAV_DEL, ""))
        if rid in favs:
            favs.remove(rid)
        await context.bot.send_message(chat_id=chat_id, text="Убрано из избранного ❌")
        return

    # ---- Удаление (только админ) ----
    if data.startswith(CB_DEL_ASK):
        if query.from_user.id != ADMIN_ID:
            await context.bot.send_message(chat_id=chat_id, text="Нет прав (только админ).")
            return

        rid = int(data.replace(CB_DEL_ASK, ""))
        r = find_recipe_by_id(recipes, rid)
        if not r:
            await context.bot.send_message(chat_id=chat_id, text="Рецепт уже удалён.")
            return

        confirm_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"{CB_DEL_OK}{rid}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"{CB_DEL_NO}{rid}"),
            ]
        ])
        await context.bot.send_message(chat_id=chat_id, text=f"Удалить рецепт «{r.title}»?", reply_markup=confirm_kb)
        return

    if data.startswith(CB_DEL_NO):
        await context.bot.send_message(chat_id=chat_id, text="Ок, не удаляю.")
        return

    if data.startswith(CB_DEL_OK):
        if query.from_user.id != ADMIN_ID:
            await context.bot.send_message(chat_id=chat_id, text="Нет прав (только админ).")
            return

        rid = int(data.replace(CB_DEL_OK, ""))
        r = find_recipe_by_id(recipes, rid)
        if not r:
            await context.bot.send_message(chat_id=chat_id, text="Рецепт уже удалён.")
            return

        # Удаляем рецепт и сохраняем
        recipes = [x for x in recipes if x.id != rid]
        context.application.bot_data["recipes"] = recipes
        save_recipes(recipes)

        # Вычищаем из избранного у всех пользователей (user_data хранится persistence)
        for _uid, udata in context.application.user_data.items():
            uf = udata.get("favs")
            if isinstance(uf, list) and rid in uf:
                uf[:] = [x for x in uf if x != rid]

        await context.bot.send_message(chat_id=chat_id, text=f"Удалено ✅: {r.title}")
        return


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Не понял. Нажми кнопку или /start.", reply_markup=MAIN_KB)


def main() -> None:
    token = os.environ.get("8282470852:AAGrIZ0tO9fRrLlocqO50EF-unbHoJ4taC4") or "8282470852:AAGrIZ0tO9fRrLlocqO50EF-unbHoJ4taC4"

    persistence = PicklePersistence(filepath=PERSISTENCE_FILE)
    app = Application.builder().token(token).persistence(persistence).build()

    add_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Добавить рецепт$"), add_start)],
        states={
            ADD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_title)],
            ADD_INGR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ingredients)],
            ADD_STEPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_steps)],
            ADD_PHOTO: [
                MessageHandler(filters.PHOTO, add_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))

    app.add_handler(MessageHandler(filters.Regex("^📚 Каталог$"), show_catalog))
    app.add_handler(CommandHandler("catalog", show_catalog))

    app.add_handler(MessageHandler(filters.Regex("^🍲 Случайный рецепт$"), random_recipe))
    app.add_handler(CommandHandler("random", random_recipe))

    app.add_handler(MessageHandler(filters.Regex("^⭐ Избранное$"), show_favs))
    app.add_handler(CommandHandler("favs", show_favs))

    app.add_handler(MessageHandler(filters.Regex("^🔎 Поиск$"), search_hint))
    app.add_handler(add_conv)

    app.add_handler(CallbackQueryHandler(on_callback))

    # Поиск по любому тексту
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_text))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    app.run_polling()


if __name__ == "__main__":
    main()
