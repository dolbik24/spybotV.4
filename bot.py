import asyncio
import random
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web

BOT_TOKEN = os.environ["BOT_TOKEN"]
REQUIRED_CHANNEL = "@spygame24"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Крошечный веб-сервер для обмана Render (чтобы он видел открытый веб-порт)
async def handle(request):
    return web.Response(text="Бот работает успешно!")

async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        return False

async def check_sub(callback: types.CallbackQuery) -> bool:
    if await is_subscribed(callback.from_user.id):
        return True
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}")],
        [types.InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")],
    ])
    await callback.answer("Нужна подписка на канал!", show_alert=True)
    try:
        await callback.message.edit_text(
            f"⛔️ Для использования бота нужно подписаться на канал {REQUIRED_CHANNEL}.\n\nПосле подписки нажми кнопку ниже.",
            reply_markup=kb
        )
    except Exception:
        await callback.message.answer(
            f"⛔️ Для использования бота нужно подписаться на канал {REQUIRED_CHANNEL}.\n\nПосле подписки нажми кнопку ниже.",
            reply_markup=kb
        )
    return False

HEROES = [
    "Abaddon", "Ancient Apparition", "Anti-Mage", "Arc Warden", "Axe",
    "Bane", "Batrider", "Beastmaster", "Bloodseeker", "Bounty Hunter",
    "Brewmaster", "Bristleback", "Broodmother", "Centaur Warrunner", "Chaos Knight",
    "Chen", "Clinkz", "Clockwerk", "Crystal Maiden", "Dark Seer",
    "Dark Willow", "Dawnbreaker", "Dazzle", "Death Prophet", "Disruptor",
    "Doom", "Dragon Knight", "Drow Ranger", "Earth Spirit", "Earthshaker",
    "Elder Titan", "Ember Spirit", "Enchantress", "Enigma", "Faceless Void",
    "Grimstroke", "Gyrocopter", "Hoodwink", "Huskar", "Invoker",
    "Io", "Jakiro", "Juggernaut", "Keeper of the Light", "Kez",
    "Kunkka", "Legion Commander", "Leshrac", "Lich", "Lifestealer",
    "Lina", "Lion", "Lone Druid", "Luna", "Lycan",
    "Magnus", "Marci", "Mars", "Medusa", "Meepo",
    "Mirana", "Monkey King", "Morphling", "Muerta", "Naga Siren",
    "Nature's Prophet", "Necrophos", "Night Stalker", "Nyx Assassin", "Ogre Magi",
    "Omniknight", "Oracle", "Outworld Destroyer", "Pangolier", "Phantom Assassin",
    "Phantom Lancer", "Phoenix", "Primal Beast", "Puck", "Pudge",
    "Pugna", "Queen of Pain", "Razor", "Riki", "Ringmaster",
    "Rubick", "Sand King", "Shadow Demon", "Shadow Fiend", "Shadow Shaman",
    "Silencer", "Skywrath Mage", "Slardar", "Slark", "Snapfire",
    "Sniper", "Spectre", "Spirit Breaker", "Storm Spirit", "Sven",
    "Techies", "Templar Assassin", "Terrorblade", "Tidehunter", "Timbersaw",
    "Tinker", "Tiny", "Treant Protector", "Troll Warlord", "Tusk",
    "Underlord", "Undying", "Ursa", "Vengeful Spirit", "Venomancer",
    "Viper", "Visage", "Void Spirit", "Warlock", "Weaver",
    "Windranger", "Winter Wyvern", "Witch Doctor", "Wraith King", "Zeus",
    "Alchemist",
]

HEROES_PER_PAGE = 20

ROOMS: dict = {}
PLAYER_TO_ROOM: dict = {}
PENDING: dict = {}

MAX_PLAYERS_MIN, MAX_PLAYERS_MAX = 3, 10
MIN_ROUNDS_MIN, MIN_ROUNDS_MAX = 1, 10

def generate_room_id():
    while True:
        rid = str(random.randint(1000, 9999))
        if rid not in ROOMS:
            return rid

def main_menu_kb():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🏰 Создать комнату", callback_data="menu_create")],
        [types.InlineKeyboardButton(text="🚪 Присоединиться к комнате", callback_data="menu_join")],
    ])

MODE_LABELS = {
    "standard": "🕵️ Стандартный шпион",
    "wrong_pick": "🎭 Ошибочный пик",
}
MODE_NEXT = {"standard": "wrong_pick", "wrong_pick": "standard"}

def room_lobby_kb(room_id: str, is_host: bool):
    if is_host:
        mode = ROOMS[room_id].get("mode", "standard")
        mode_label = MODE_LABELS[mode]
        rows = [
            [types.InlineKeyboardButton(text="🚀 НАЧАТЬ ИГРУ", callback_data=f"startgame_{room_id}")],
            [types.InlineKeyboardButton(text="🔄 Обновить список", callback_data=f"refresh_{room_id}")],
            [types.InlineKeyboardButton(text=f"Режим: {mode_label}", callback_data=f"togglemode_{room_id}")],
            [types.InlineKeyboardButton(text="⚙️ Настройки комнаты", callback_data=f"settings_{room_id}")],
            [types.InlineKeyboardButton(text="👢 Кикнуть игрока", callback_data=f"kickmenu_{room_id}")],
            [types.InlineKeyboardButton(text="💥 Распустить комнату", callback_data=f"dissolve_{room_id}")],
        ]
    else:
        rows = [
            [types.InlineKeyboardButton(text="🔄 Обновить список", callback_data=f"refresh_{room_id}")],
            [types.InlineKeyboardButton(text="🚪 Покинуть комнату", callback_data=f"leave_{room_id}")],
        ]
    return types.InlineKeyboardMarkup(inline_keyboard=rows)

def settings_kb(room_id: str) -> types.InlineKeyboardMarkup:
    room = ROOMS[room_id]
    max_p = room["max_players"]
    min_r = room["min_rounds"]
    pwd = room.get("password")
    pwd_status = "🔑 Пароль: ✅ установлен" if pwd else "🔑 Пароль: не установлен"

    rows = [
        [types.InlineKeyboardButton(text=f"👥 Максимум игроков: {max_p}", callback_data="noop")],
        [
            types.InlineKeyboardButton(text="➖", callback_data=f"sett_{room_id}_maxp_dec"),
            types.InlineKeyboardButton(text=str(max_p), callback_data="noop"),
            types.InlineKeyboardButton(text="➕", callback_data=f"sett_{room_id}_maxp_inc"),
        ],
        [types.InlineKeyboardButton(text=f"🔄 Кругов до голосования: {min_r}", callback_data="noop")],
        [
            types.InlineKeyboardButton(text="➖", callback_data=f"sett_{room_id}_rnd_dec"),
            types.InlineKeyboardButton(text=str(min_r), callback_data="noop"),
            types.InlineKeyboardButton(text="➕", callback_data=f"sett_{room_id}_rnd_inc"),
        ],
        [types.InlineKeyboardButton(text=pwd_status, callback_data="noop")],
        [types.InlineKeyboardButton(text="✏️ Установить / изменить пароль", callback_data=f"sett_{room_id}_pwd_set")],
    ]
    if pwd:
        rows.append([types.InlineKeyboardButton(text="❌ Убрать пароль", callback_data=f"sett_{room_id}_pwd_clr")])
    rows.append([types.InlineKeyboardButton(text="🔙 Назад в лобби", callback_data=f"settback_{room_id}")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)

def heroes_page_kb(room_id: str, page: int) -> types.InlineKeyboardMarkup:
    start = page * HEROES_PER_PAGE
    end = min(start + HEROES_PER_PAGE, len(HEROES))
    total_pages = (len(HEROES) + HEROES_PER_PAGE - 1) // HEROES_PER_PAGE

    buttons = []
    row = []
    for i, hero in enumerate(HEROES[start:end]):
        idx = start + i
        row.append(types.InlineKeyboardButton(text=hero, callback_data=f"vote_{room_id}_{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(text="◀️", callback_data=f"spypage_{room_id}_{page - 1}"))
    nav.append(types.InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(types.InlineKeyboardButton(text="▶️", callback_data=f"spypage_{room_id}_{page + 1}"))
    buttons.append(nav)

    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def suspect_kb(room_id: str, voter_id: int) -> types.InlineKeyboardMarkup:
    room = ROOMS[room_id]
    rows = []
    for p_id in room["players"]:
        if p_id == voter_id:
            continue
        rows.append([types.InlineKeyboardButton(
            text=f"🎯 {room['names'][p_id]}",
            callback_data=f"svote_{room_id}_{p_id}"
        )])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)

def lobby_text(room_id: str) -> str:
    room = ROOMS[room_id]
    pwd = room.get("password")
    lock = "🔒" if pwd else "🔓"
    mode = room.get("mode", "standard")
    mode_label = MODE_LABELS[mode]
    text = (
        f"🏰 **Комната №{room_id}** {lock}\n"
        f"👥 Игроков: {len(room['players'])}/{room['max_players']} | "
        f"🔄 Кругов до голос.: {room['min_rounds']}\n"
        f"Режим: {mode_label}\n\n"
        f"**Участники:**\n"
    )
    for p_id in room["players"]:
        crown = " 👑" if p_id == room["host"] else ""
        text += f"• {room['names'][p_id]}{crown}\n"
    return text

def peaceful_players(room: dict) -> list:
    return [p for p in room["players"] if p != room["spy"]]

async def notify_current_player(room_id: str):
    room = ROOMS[room_id]
    idx = room["turn_idx"]
    order = room["turn_order"]
    current_id = order[idx]
    current_name = room["names"][current_id]
    total = len(order)
    round_num = room["round_num"]

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Я ответил — передаю ход", callback_data=f"nextturn_{room_id}")]
    ])

    for p_id in room["players"]:
        try:
            if p_id == current_id:
                await bot.send_message(
                    p_id,
                    f"🎤 **Твоя очередь!**\n_(Круг {round_num}, ход {idx + 1}/{total})_\n\nДай подсказку голосом и нажми кнопку.",
                    reply_markup=kb, parse_mode="Markdown"
                )
            else:
                await bot.send_message(
                    p_id,
                    f"🎤 Отвечает **{current_name}** _(Круг {round_num}, ход {idx + 1}/{total})_",
                    parse_mode="Markdown"
                )
        except Exception:
            pass

async def open_round_vote(room_id: str):
    room = ROOMS[room_id]
    room["phase"] = "round_vote"
    room["round_votes"] = {}

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 Продолжить круги", callback_data=f"rvote_{room_id}_continue")],
        [types.InlineKeyboardButton(text="🗳️ Голосовать за шпиона", callback_data=f"rvote_{room_id}_final")],
    ])

    for p_id in room["players"]:
        try:
            await bot.send_message(
                p_id,
                f"⏸ **Круг {room['round_num'] - 1} завершён!**\n\nПродолжить обсуждение или уже голосовать за шпиона?",
                reply_markup=kb, parse_mode="Markdown"
            )
        except Exception:
            pass

async def open_final_vote(room_id: str):
    room = ROOMS[room_id]
    room["phase"] = "final_vote"
    room["votes"] = {}
    room["spy_guess"] = None

    for p_id in room["players"]:
        try:
            await bot.send_message(
                p_id,
                "🗳️ **ФИНАЛЬНОЕ ГОЛОСОВАНИЕ!**\n\nКаждый голосует за того, кто кажется шпионом.\n"
                "_(Шпион тоже голосует — чтобы замести следы!)_\n\nКто шпион?",
                reply_markup=suspect_kb(room_id, p_id),
                parse_mode="Markdown"
            )
        except Exception:
            pass

async def open_spy_guessing(room_id: str, vote_summary: str):
    room = ROOMS[room_id]
    room["phase"] = "spy_guessing"
    spy_id = room["spy"]
    total_pages = (len(HEROES) + HEROES_PER_PAGE - 1) // HEROES_PER_PAGE

    for p_id in room["players"]:
        try:
            if p_id == spy_id:
                await bot.send_message(
                    p_id,
                    f"🗳️ **Результат голосования:**\n{vote_summary}\n\n"
                    f"🕵️ Теперь твой ход! Угадай секретного героя.\n"
                    f"Если угадаешь — победишь, даже если тебя вычислили!\n\n"
                    f"**Выбери героя (стр. 1/{total_pages}):**",
                    reply_markup=heroes_page_kb(room_id, 0),
                    parse_mode="Markdown"
                )
            else:
                await bot.send_message(
                    p_id,
                    f"🗳️ **Результат голосования:**\n{vote_summary}\n\n"
                    f"⏳ Шпион выбирает героя... Ждите!",
                    parse_mode="Markdown"
                )
        except Exception:
            pass

async def resolve_after_spy_guess(room_id: str):
    room = ROOMS[room_id]
    if room.get("game_over"):
        return

    spy_id = room["spy"]
    spy_name = room["names"][spy_id]
    correct_hero = room["hero"]
    chosen_hero = room["spy_guess"]
    spy_correct = (chosen_hero == correct_hero)

    vote_count: dict = {}
    for suspect_id in room["votes"].values():
        vote_count[suspect_id] = vote_count.get(suspect_id, 0) + 1

    accused_id = max(vote_count, key=lambda x: vote_count[x]) if vote_count else None
    accused_name = room["names"].get(accused_id, "???") if accused_id else "???"
    vote_correct = (accused_id == spy_id)

    vote_summary = "\n".join(
        f"• {room['names'][pid]}: {cnt} гол."
        for pid, cnt in sorted(vote_count.items(), key=lambda x: -x[1])
    ) if vote_count else "—"

    spy_line = f"Шпион выбрал: **{chosen_hero}** — {'✅ угадал!' if spy_correct else '❌ ошибся'}"
    vote_line = (
        f"Голоса:\n{vote_summary}\n"
        f"Выбрали: **{accused_name}** — {'✅ это шпион!' if vote_correct else '❌ не шпион'}"
    )

    if spy_correct:
        result = f"🗳️ {vote_line}\n\n🕵️ {spy_line}\n\n🎉 **ШПИОН ПОБЕДИЛ!**\n{spy_name} угадал героя **{correct_hero}**!"
    elif vote_correct:
        result = f"🗳️ {vote_line}\n\n🕵️ {spy_line}\n\n🎉 **МИРНЫЕ ПОБЕДИЛИ!**\nШпион {spy_name} разоблачён, герой был **{correct_hero}**."
    else:
        result = f"🗳️ {vote_line}\n\n🕵️ {spy_line}\n\n💥 **ШПИОН ПОБЕДИЛ!**\nМирные ошиблись, герой был **{correct_hero}**."

    await finish_game(room_id, result)

async def finish_game(room_id: str, result_text: str):
    if room_id not in ROOMS:
        return
    room = ROOMS[room_id]
    room.update({
        "game_over": True, "active": False, "phase": "lobby",
        "spy": None, "hero": None, "spy_hero": None, "voting_open": False,
        "votes": {}, "spy_guess": None, "round_votes": {},
        "turn_idx": 0, "round_num": 0,
        "awaiting_ack": set(room["players"]),
    })

    after_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 Остаться в комнате", callback_data=f"stayroom_{room_id}")],
        [types.InlineKeyboardButton(text="🚪 Покинуть комнату", callback_data=f"quitroom_{room_id}")]
    ])
    host_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 Сыграть ещё", callback_data=f"stayroom_{room_id}")],
        [types.InlineKeyboardButton(text="💥 Распустить комнату", callback_data=f"dissolve_{room_id}")]
    ])

    for p_id in room["players"]:
        kb = host_kb if p_id == room["host"] else after_kb
        try:
            await bot.send_message(p_id, f"🏁 **Игра окончена!**\n\n{result_text}\n\nЧто дальше?",
                                   reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    PENDING.pop(user_id, None)

    if not await is_subscribed(user_id):
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}")],
            [types.InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")],
        ])
        await message.answer(
            f"⛔️ Для использования бота нужно подписаться на канал {REQUIRED_CHANNEL}.\n\nПосле подписки нажми кнопку ниже.",
            reply_markup=kb
        )
        return

    if user_id in PLAYER_TO_ROOM:
        room_id = PLAYER_TO_ROOM[user_id]
        room = ROOMS.get(room_id)
        if room:
            await message.answer(lobby_text(room_id),
                                 reply_markup=room_lobby_kb(room_id, user_id == room["host"]),
                                 parse_mode="Markdown")
            return

    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nВыбери действие:",
        reply_markup=main_menu_kb(), parse_mode="Markdown"
    )

@dp.message(F.text)
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    pending = PENDING.get(user_id)
    if not pending:
        return

    action = pending["action"]
    room_id = pending["room_id"]
    PENDING.pop(user_id, None)

    if action == "set_password":
        if room_id not in ROOMS:
            await message.answer("Комната больше не существует.")
            return
        room = ROOMS[room_id]
        if user_id != room["host"]:
            return
        pwd = message.text.strip()
        if len(pwd) < 1 or len(pwd) > 32:
            await message.answer("Пароль должен быть от 1 до 32 символов. Попробуй ещё раз.")
            return
        room["password"] = pwd
        await message.answer(
            f"✅ Пароль установлен: `{pwd}`\n\nТеперь для входа в комнату игроки должны знать его.",
            parse_mode="Markdown"
        )
        await message.answer(lobby_text(room_id),
                             reply_markup=room_lobby_kb(room_id, True),
                             parse_mode="Markdown")

    elif action == "enter_password":
        if room_id not in ROOMS:
            await message.answer("Комната больше не существует.", reply_markup=main_menu_kb())
            return
        room = ROOMS[room_id]
        entered = message.text.strip()

        if entered != room.get("password"):
            await message.answer("❌ Неверный пароль! Попробуй ещё раз или вернись в меню.",
                                 reply_markup=main_menu_kb())
            return

        if user_id in PLAYER_TO_ROOM:
            await message.answer("Ты уже в другой комнате!")
            return
        if room["active"]:
            await message.answer("Игра уже началась!", reply_markup=main_menu_kb())
            return
        if len(room["players"]) >= room["max_players"]:
            await message.answer("Комната заполнена.", reply_markup=main_menu_kb())
            return

        room["players"].append(user_id)
        room["names"][user_id] = message.from_user.full_name
        PLAYER_TO_ROOM[user_id] = room_id

        await message.answer(
            f"✅ Пароль верный! Ты вошёл в комнату №{room_id}.\n\n" + lobby_text(room_id),
            reply_markup=room_lobby_kb(room_id, False),
            parse_mode="Markdown"
        )
        try:
            await bot.send_message(room["host"], f"➕ {message.from_user.full_name} присоединился к комнате №{room_id}!")
        except Exception:
            pass

@dp.callback_query(F.data == "check_sub")
async def handle_check_sub(callback: types.CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.message.edit_text("Привет! Выбери действие:", reply_markup=main_menu_kb())
        await callback.answer("Подписка подтверждена!")
    else:
        await callback.answer("Ты ещё не подписан на канал!", show_alert=True)

@dp.callback_query(F.data == "menu_create")
async def menu_create(callback: types.CallbackQuery):
    if not await check_sub(callback):
        return
    user_id = callback.from_user.id
    if user_id in PLAYER_TO_ROOM:
        await callback.answer("Ты уже в комнате!", show_alert=True)
        return

    room_id = generate_room_id()
    ROOMS[room_id] = {
        "host": user_id,
        "players": [user_id],
        "names": {user_id: callback.from_user.full_name},
        "spy": None, "hero": None,
        "active": False, "game_over": False,
        "phase": "lobby",
        "turn_order": [], "turn_idx": 0, "round_num": 0,
        "round_votes": {}, "votes": {}, "spy_guess": None,
        "voting_open": False,
        "password": None,
        "max_players": 6,
        "min_rounds": 2,
        "mode": "standard",
        "spy_hero": None,
    }
    PLAYER_TO_ROOM[user_id] = room_id

    await callback.message.edit_text(lobby_text(room_id),
                                     reply_markup=room_lobby_kb(room_id, True),
                                     parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "menu_join")
async def menu_join(callback: types.CallbackQuery):
    if not await check_sub(callback):
        return
    user_id = callback.from_user.id
    if user_id in PLAYER_TO_ROOM:
        await callback.answer("Ты уже в комнате!", show_alert=True)
        return

    open_rooms = {rid: r for rid, r in ROOMS.items()
                  if not r["active"] and len(r["players"]) < r["max_players"]}
    if not open_rooms:
        await callback.answer("Нет доступных комнат. Создай свою!", show_alert=True)
        return

    rows = []
    for rid, r in open_rooms.items():
        host_name = r["names"][r["host"]]
        lock = "🔒 " if r.get("password") else ""
        rows.append([types.InlineKeyboardButton(
            text=f"{lock}Комната №{rid} — {host_name} ({len(r['players'])}/{r['max_players']})",
            callback_data=f"joinroom_{rid}"
        )])
    rows.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")])

    await callback.message.edit_text("🚪 **Выбери комнату:**\n_(🔒 — требуется пароль)_",
                                     reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
                                     parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "menu_back")
async def menu_back(callback: types.CallbackQuery):
    await callback.message.edit_text("Выбери действие:", reply_markup=main_menu_kb())
    await callback.answer()

@dp.callback_query(F.data.startswith("joinroom_"))
async def join_room(callback: types.CallbackQuery):
    if not await check_sub(callback):
        return
    user_id = callback.from_user.id
    room_id = callback.data.split("_")[1]

    if user_id in PLAYER_TO_ROOM:
        await callback.answer("Ты уже в комнате!", show_alert=True)
        return
    if room_id not in ROOMS:
        await callback.answer("Комната не существует.", show_alert=True)
        return

    room = ROOMS[room_id]
    if room["active"]:
        await callback.answer("Игра уже началась!", show_alert=True)
        return
    if len(room["players"]) >= room["max_players"]:
        await callback.answer(f"Комната заполнена ({room['max_players']}/{room['max_players']}).", show_alert=True)
        return

    if room.get("password"):
        PENDING[user_id] = {"action": "enter_password", "room_id": room_id}
        await callback.message.edit_text(
            f"🔒 Комната №{room_id} защищена паролем.\n\nНапиши пароль в чат:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 Отмена", callback_data="menu_back")]
            ])
        )
        await callback.answer()
        return

    room["players"].append(user_id)
    room["names"][user_id] = callback.from_user.full_name
    PLAYER_TO_ROOM[user_id] = room_id

    await callback.message.edit_text(lobby_text(room_id),
                                     reply_markup=room_lobby_kb(room_id, False),
                                     parse_mode="Markdown")
    await callback.answer(f"Ты вошёл в комнату №{room_id}!")
    try:
        await bot.send_message(room["host"], f"➕ {callback.from_user.full_name} присоединился к комнате №{room_id}!")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("togglemode_"))
async def toggle_mode(callback: types.CallbackQuery):
    room_id = callback.data.split("_")[1]
    if room_id not in ROOMS:
        await callback.answer("Комната не найдена.")
        return
    room = ROOMS[room_id]
    if callback.from_user.id != room["host"]:
        await callback.answer("Только хост может менять режим.", show_alert=True)
        return
    if room["active"]:
        await callback.answer("Нельзя менять режим во время игры.", show_alert=True)
        return

    current = room.get("mode", "standard")
    room["mode"] = MODE_NEXT[current]
    new_label = MODE_LABELS[room["mode"]]

    try:
        await callback.message.edit_text(lobby_text(room_id),
                                         reply_markup=room_lobby_kb(room_id, True),
                                         parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer(f"Режим: {new_label}")

@dp.callback_query(F.data.startswith("settings_"))
async def open_settings(callback: types.CallbackQuery):
    room_id = callback.data.split("_")[1]
    if room_id not in ROOMS:
        await callback.answer("Комната не найдена.")
        return
    room = ROOMS[room_id]
    if callback.from_user.id != room["host"]:
        await callback.answer("Только хост может открыть настройки.", show_alert=True)
        return

    await callback.message.edit_text(
        f"⚙️ **Настройки комнаты №{room_id}**\n\n"
        f"Здесь ты можешь изменить правила игры:",
        reply_markup=settings_kb(room_id),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("settback_"))
async def settings_back(callback: types.CallbackQuery):
    room_id = callback.data.split("_")[1]
    if room_id not in ROOMS:
        await callback.answer("Комната не найдена.")
        return
    await callback.message.edit_text(lobby_text(room_id),
                                     reply_markup=room_lobby_kb(room_id, True),
                                     parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("sett_"))
async def handle_setting(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    room_id = parts[1]
    key = parts[2]
    action = parts[3]
    user_id = callback.from_user.id

    if room_id not in ROOMS:
        await callback.answer("Комната не найдена.")
        return
    room = ROOMS[room_id]
    if user_id != room["host"]:
        await callback.answer("Только хост может менять настройки.", show_alert=True)
        return

    if key == "maxp":
        val = room["max_players"]
        if action == "inc" and val < MAX_PLAYERS_MAX:
            room["max_players"] = val + 1
        elif action == "dec" and val > max(MAX_PLAYERS_MIN, len(room["players"])):
            room["max_players"] = val - 1
        else:
            await callback.answer(f"Предел: {MAX_PLAYERS_MIN}–{MAX_PLAYERS_MAX} (не меньше числа игроков в комнате).")
            return

    elif key == "rnd":
        val = room["min_rounds"]
        if action == "inc" and val < MIN_ROUNDS_MAX:
            room["min_rounds"] = val + 1
        elif action == "dec" and val > MIN_ROUNDS_MIN:
            room["min_rounds"] = val - 1
        else:
            await callback.answer(f"Предел: {MIN_ROUNDS_MIN}–{MIN_ROUNDS_MAX}.")
            return

    elif key == "pwd":
        if action == "set":
            PENDING[user_id] = {"action": "set_password", "room_id": room_id}
            await callback.message.edit_text(
                "🔑 Напиши новый пароль в чат (1–32 символа):",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🔙 Отмена", callback_data=f"settback_{room_id}")]
                ])
            )
            await callback.answer()
            return
        elif action == "clr":
            room["password"] = None
            await callback.answer("Пароль удалён.")

    try:
        await callback.message.edit_reply_markup(reply_markup=settings_kb(room_id))
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("kickmenu_"))
async def kick_menu(callback: types.CallbackQuery):
    room_id = callback.data.split("_")[1]
    user_id = callback.from_user.id

    if room_id not in ROOMS:
        await callback.answer("Комната не найдена.")
        return
    room = ROOMS[room_id]
    if user_id != room["host"]:
        await callback.answer("Только хост может кикать.", show_alert=True)
        return

    others = [p for p in room["players"] if p != user_id]
    if not others:
        await callback.answer("Больше некого кикать — ты один в комнате.", show_alert=True)
        return

    rows = []
    for p_id in others:
        rows.append([types.InlineKeyboardButton(
            text=f"❌ {room['names'][p_id]}",
            callback_data=f"kick_{room_id}_{p_id}"
        )])
    rows.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"kickback_{room_id}")])

    await callback.message.edit_text(
        "👢 **Выбери игрока для кика:**",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("kickback_"))
async def kick_back(callback: types.CallbackQuery):
    room_id = callback.data.split("_")[1]
    if room_id not in ROOMS:
        await callback.answer("Комната не найдена.")
        return
    await callback.message.edit_text(lobby_text(room_id),
                                     reply_markup=room_lobby_kb(room_id, True),
                                     parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("kick_"))
async def kick_player(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    room_id = parts[1]
    target_id = int(parts[2])
    host_id = callback.from_user.id

    if room_id not in ROOMS:
        await callback.answer("Комната не найдена.")
        return
    room = ROOMS[room_id]
    if host_id != room["host"]:
        await callback.answer("Только хост может кикать.", show_alert=True)
        return
    if target_id not in room["players"]:
        await callback.answer("Этот игрок уже не в комнате.")
        return

    target_name = room["names"].get(target_id, "???")
    room["players"].remove(target_id)
    room["names"].pop(target_id, None)
    PLAYER_TO_ROOM.pop(target_id, None)

    await callback.message.edit_text(lobby_text(room_id),
                                     reply_markup=room_lobby_kb(room_id, True),
                                     parse_mode="Markdown")
    await callback.answer(f"{target_name} кикнут!")

    try:
        await bot.send_message(
            target_id,
            f"🚫 Тебя кикнул хост из комнаты №{room_id}.",
            reply_markup=main_menu_kb()
        )
    except Exception:
        pass

@dp.callback_query(F.data.startswith("refresh_"))
async def refresh_room(callback: types.CallbackQuery):
    room_id = callback.data.split("_")[1]
    if room_id not in ROOMS:
        await callback.answer("Комната не существует.", show_alert=True)
        return
    room = ROOMS[room_id]
    try:
        await callback.message.edit_text(lobby_text(room_id),
                                         reply_markup=room_lobby_kb(room_id, callback.from_user.id == room["host"]),
                                         parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer("Обновлено!")

@dp.callback_query(F.data.startswith("leave_"))
async def leave_room(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    room_id = callback.data.split("_")[1]

    if room_id not in ROOMS:
        await callback.answer("Комната не найдена.")
        return
    room = ROOMS[room_id]
    if user_id not in room["players"]:
        await callback.answer("Ты не в этой комнате.")
        return

    room["players"].remove(user_id)
    room["names"].pop(user_id, None)
    PLAYER_TO_ROOM.pop(user_id, None)

    await callback.message.edit_text("Ты покинул комнату.", reply_markup=main_menu_kb())
    await callback.answer()
    try:
        await bot.send_message(room["host"], f"➖ {callback.from_user.full_name} покинул комнату №{room_id}.")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("dissolve_"))
async def dissolve_room(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    room_id = callback.data.split("_")[1]

    if room_id not in ROOMS:
        await callback.answer("Комната не найдена.")
        return
    room = ROOMS[room_id]
    if user_id != room["host"]:
        await callback.answer("Только создатель может распустить комнату!", show_alert=True)
        return

    players = list(room["players"])
    for p_id in players:
        PLAYER_TO_ROOM.pop(p_id, None)
    del ROOMS[room_id]

    await callback.message.edit_text("💥 Комната распущена.", reply_markup=main_menu_kb())
    await callback.answer()

    for p_id in players:
        if p_id == user_id:
            continue
        try:
            await bot.send_message(p_id, f"💥 Комната №{room_id} распущена хостом.", reply_markup=main_menu_kb())
        except Exception:
            pass

@dp.callback_query(F.data.startswith("startgame_"))
async def start_game(callback: types.CallbackQuery):
    room_id = callback.data.split("_")[1]
    if room_id not in ROOMS:
        await callback.answer("Комната не найдена.")
        return
    room = ROOMS[room_id]

    if callback.from_user.id != room["host"]:
        await callback.answer("Только создатель может запустить игру!", show_alert=True)
        return

    pending = room.get("awaiting_ack", set())
    if pending:
        names = ", ".join(room["names"].get(p, "???") for p in pending)
        await callback.answer(
            f"Не все игроки завершили предыдущую игру:\n{names}",
            show_alert=True
        )
        return

    count = len(room["players"])
    if count < 3:
        await callback.answer(f"Нужно минимум 3 игрока! Сейчас: {count}.", show_alert=True)
        return

    mode = room.get("mode", "standard")
    spy_id = random.choice(room["players"])
    turn_order = random.sample(room["players"], len(room["players"]))
    min_rounds = room["min_rounds"]

    if mode == "wrong_pick":
        main_hero = random.choice(HEROES)
        spy_hero = random.choice([h for h in HEROES if h != main_hero])
    else:
        main_hero = random.choice(HEROES)
        spy_hero = None

    room.update({
        "active": True, "game_over": False,
        "hero": main_hero, "spy": spy_id, "spy_hero": spy_hero,
        "phase": "rounds",
        "turn_order": turn_order, "turn_idx": 0, "round_num": 1,
        "round_votes": {}, "votes": {}, "spy_guess": None,
        "voting_open": False,
    })

    await callback.message.edit_text(f"🎲 Роли распределены! {count} игроков. Круг 1 из минимум {min_rounds}...")
    await callback.answer()

    for p_id in room["players"]:
        try:
            if mode == "wrong_pick":
                hero_for_player = spy_hero if p_id == spy_id else main_hero
                await bot.send_message(p_id,
                    f"🎭 **Режим: Ошибочный пик**\n\n"
                    f"🎯 Твой герой: `{hero_for_player}`\n\n"
                    f"Кто-то из игроков получил другого героя. "
                    f"Называй факты о своём герое и вычисли, у кого другой!\n\n"
                    f"_Никто не знает свою роль._",
                    parse_mode="Markdown")
            else:
                if p_id == spy_id:
                    await bot.send_message(p_id,
                        "🔴 **ТВОЯ РОЛЬ: ШПИОН** 🕵️\n\nТы не знаешь секретного героя. "
                        "Слушай подсказки и не раскрывай себя!\n\n"
                        f"_После {min_rounds} кругов будет голосование._",
                        parse_mode="Markdown")
                else:
                    await bot.send_message(p_id,
                        f"🟢 **ТВОЯ РОЛЬ: МИРНЫЙ ИГРОК**\n\nСекретного героя: `{main_hero}`\n\n"
                        f"Давай подсказки по очереди!",
                        parse_mode="Markdown")
        except Exception:
            pass

    await notify_current_player(room_id)

@dp.callback_query(F.data.startswith("nextturn_"))
async def next_turn(callback: types.CallbackQuery):
    room_id = callback.data.split("_")[1]
    if room_id not in ROOMS:
        await callback.answer("Игра завершена.")
        return

    room = ROOMS[room_id]
    if room.get("game_over") or room["phase"] != "rounds":
        await callback.answer("Сейчас не фаза ходов.")
        return

    current_id = room["turn_order"][room["turn_idx"]]
    if callback.from_user.id != current_id:
        await callback.answer("Сейчас не твой ход!", show_alert=True)
        return

    try:
        await callback.message.edit_text(f"✅ Ответил в круге {room['round_num']}.")
    except Exception:
        pass
    await callback.answer()

    room["turn_idx"] += 1

    if room["turn_idx"] >= len(room["turn_order"]):
        finished_round = room["round_num"]
        room["round_num"] += 1
        room["turn_idx"] = 0

        for p_id in room["players"]:
            try:
                await bot.send_message(p_id, f"🔔 Круг {finished_round} завершён!")
            except Exception:
                pass

        if finished_round >= room["min_rounds"]:
            await open_round_vote(room_id)
        else:
            await notify_current_player(room_id)
    else:
        await notify_current_player(room_id)

@dp.callback_query(F.data.startswith("rvote_"))
async def round_vote(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    room_id = parts[1]
    choice = parts[2]
    user_id = callback.from_user.id

    if room_id not in ROOMS:
        await callback.answer("Игра завершена.")
        return
    room = ROOMS[room_id]

    if room.get("game_over") or room["phase"] != "round_vote":
        await callback.answer("Голосование сейчас недоступно.")
        return
    if user_id not in room["players"]:
        await callback.answer("Ты не в этой игре!")
        return
    if user_id in room["round_votes"]:
        await callback.answer("Ты уже проголосовал!", show_alert=True)
        return

    room["round_votes"][user_id] = choice
    label = "продолжение" if choice == "continue" else "финал"

    try:
        await callback.message.edit_text(f"✅ Ты проголосовал за **{label}**. Ожидаем остальных...",
                                         parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer(f"Голос принят: {label}")

    if len(room["round_votes"]) < len(room["players"]):
        return

    votes = list(room["round_votes"].values())
    final_count = votes.count("final")
    continue_count = votes.count("continue")

    if final_count > continue_count:
        for p_id in room["players"]:
            try:
                await bot.send_message(p_id,
                    f"🗳️ Результат: {final_count} за финал, {continue_count} за продолжение.\n➡️ **Финальное голосование!**",
                    parse_mode="Markdown")
            except Exception:
                pass
        await open_final_vote(room_id)
    else:
        room["phase"] = "rounds"
        room["round_votes"] = {}
        for p_id in room["players"]:
            try:
                await bot.send_message(p_id,
                    f"🔄 Результат: {continue_count} за продолжение, {final_count} за финал.\n➡️ **Продолжаем! Круг {room['round_num']}...**",
                    parse_mode="Markdown")
            except Exception:
                pass
        await notify_current_player(room_id)

@dp.callback_query(F.data.startswith("spypage_"))
async def spy_page_turn(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    room_id = parts[1]
    page = int(parts[2])

    if room_id not in ROOMS:
        await callback.answer("Игра завершена.")
        return
    room = ROOMS[room_id]
    if callback.from_user.id != room["spy"]:
        await callback.answer("Ты не шпион!", show_alert=True)
        return
    if room["phase"] != "spy_guessing":
        await callback.answer("Сейчас не твоя фаза.")
        return

    total_pages = (len(HEROES) + HEROES_PER_PAGE - 1) // HEROES_PER_PAGE
    await callback.message.edit_text(
        f"🕵️ **Выбери героя (стр. {page + 1}/{total_pages}).**\nУ тебя ОДНА попытка!",
        reply_markup=heroes_page_kb(room_id, page), parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()

@dp.callback_query(F.data.startswith("vote_"))
async def spy_hero_pick(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    room_id = parts[1]
    hero_idx = int(parts[2])
    chosen_hero = HEROES[hero_idx]

    if room_id not in ROOMS:
        await callback.answer("Игра окончена.")
        return
    room = ROOMS[room_id]

    if room.get("game_over"):
        await callback.answer("Игра уже завершена.")
        return
    if room["phase"] != "spy_guessing":
        await callback.answer("Сейчас не фаза выбора героя.")
        return
    if callback.from_user.id != room["spy"]:
        await callback.answer("Только шпион выбирает героя!")
        return
    if room["spy_guess"] is not None:
        await callback.answer("Ты уже сделал выбор!")
        return

    room["spy_guess"] = chosen_hero
    correct = chosen_hero == room["hero"]

    try:
        await callback.message.edit_text(
            f"✅ Ты выбрал **{chosen_hero}** — {'угадал! ✅' if correct else 'ошибся ❌'}\nРезультат скоро...",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await callback.answer()
    await resolve_after_spy_guess(room_id)

@dp.callback_query(F.data.startswith("svote_"))
async def all_player_vote(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    room_id = parts[1]
    suspect_id = int(parts[2])
    voter_id = callback.from_user.id

    if room_id not in ROOMS:
        await callback.answer("Игра завершена.")
        return
    room = ROOMS[room_id]

    if room.get("game_over"):
        await callback.answer("Игра уже завершена.")
        return
    if room["phase"] != "final_vote":
        await callback.answer("Голосование сейчас недоступно.")
        return
    if voter_id not in room["players"]:
        await callback.answer("Ты не в этой игре!")
        return
    if voter_id in room["votes"]:
        await callback.answer("Ты уже проголосовал!", show_alert=True)
        return

    room["votes"][voter_id] = suspect_id
    suspect_name = room["names"].get(suspect_id, "???")

    try:
        await callback.message.edit_text(
            f"✅ Ты проголосовал за **{suspect_name}**.\nОжидаем остальных...",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await callback.answer(f"Голос за {suspect_name} принят!")

    if len(room["votes"]) < len(room["players"]):
        return

    vote_count: dict = {}
    for sid in room["votes"].values():
        vote_count[sid] = vote_count.get(sid, 0) + 1

    max_votes = max(vote_count.values())
    leaders = [pid for pid, cnt in vote_count.items() if cnt == max_votes]

    vote_summary = "\n".join(
        f"• {room['names'][pid]}: {cnt} гол."
        for pid, cnt in sorted(vote_count.items(), key=lambda x: -x[1])
    )

    if len(leaders) > 1:
        room["phase"] = "rounds"
        room["votes"] = {}
        for p_id in room["players"]:
            try:
                await bot.send_message(
                    p_id,
                    f"🗳️ **Ничья в голосовании!**\n{vote_summary}\n\n🔄 Игра продолжается — Круг {room['round_num']}...",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        await notify_current_player(room_id)
    elif room.get("mode") == "wrong_pick":
        accused_id = leaders[0]
        accused_name = room["names"].get(accused_id, "???")
        spy_id = room["spy"]
        spy_name = room["names"][spy_id]
        main_hero = room["hero"]
        spy_hero = room.get("spy_hero", "???")
        vote_correct = (accused_id == spy_id)

        if vote_correct:
            result = (
                f"🗳️ **Результат голосования:**\n{vote_summary}\n\n"
                f"Выбрали: **{accused_name}** — ✅ это тот самый!\n\n"
                f"🎉 **МИРНЫЕ ПОБЕДИЛИ!**\n"
                f"У большинства был герой: `{main_hero}`\n"
                f"У **{spy_name}** был другой герой: `{spy_hero}`"
            )
        else:
            result = (
                f"🗳️ **Результат голосования:**\n{vote_summary}\n\n"
                f"Выбрали: **{accused_name}** — ❌ это не тот!\n\n"
                f"💥 **ОШИБОЧНЫЙ ПИК ПОБЕДИЛ!**\n"
                f"У большинства был герой: `{main_hero}`\n"
                f"У **{spy_name}** был другой герой: `{spy_hero}`"
            )
        await finish_game(room_id, result)
    else:
        await open_spy_guessing(room_id, vote_summary)

@dp.callback_query(F.data.startswith("stayroom_"))
async def stay_in_room(callback: types.CallbackQuery):
    room_id = callback.data.split("_")[1]
    if room_id not in ROOMS:
        await callback.message.edit_text("Комната не существует.", reply_markup=main_menu_kb())
        await callback.answer()
        return

    room = ROOMS[room_id]
    room.get("awaiting_ack", set()).discard(callback.from_user.id)
    is_host = callback.from_user.id == room["host"]
    await callback.message.edit_text(lobby_text(room_id),
                                     reply_markup=room_lobby_kb(room_id, is_host),
                                     parse_mode="Markdown")
    await callback.answer("Остался в комнате!")

@dp.callback_query(F.data.startswith("quitroom_"))
async def quit_room(callback: types.CallbackQuery):
    room_id = callback.data.split("_")[1]
    user_id = callback.from_user.id

    if room_id in ROOMS:
        room = ROOMS[room_id]
        room.get("awaiting_ack", set()).discard(user_id)
        if user_id in room["players"]:
            room["players"].remove(user_id)
            room["names"].pop(user_id, None)
        try:
            await bot.send_message(room["host"],
                f"➖ {callback.from_user.full_name} покинул комнату №{room_id}.")
        except Exception:
            pass

    PLAYER_TO_ROOM.pop(user_id, None)
    await callback.message.edit_text("Ты покинул комнату.", reply_markup=main_menu_kb())
    await callback.answer()

# Главная асинхронная точка входа
async def start_bot():
    print("Spy Game Бот запущен!")
    await dp.start_polling(bot)

async def main():
    # Запускаем поллинг бота в фоновом таске
    asyncio.create_task(start_bot())
    
    # Настраиваем веб-сервер для удержания порта на Render
    app = web.Application()
    app.router.add_get('/', handle)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Переменная PORT подставляется Render автоматически
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    # Поддерживаем бесконечную работу приложения
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
