import logging

from aioredis import create_redis_pool, Redis
from aiotg import Chat, Bot

from trading_bot.manager import Manager, State
from trading_bot.settings import dev_hooks_token, chatbase_token, proxy_string
from trading_bot.sources.sources import SmartLab
from trading_bot.telegram_helper import keyboard_markup, build_menu

log = logging.getLogger(__name__)

bot = Bot(
    api_token=dev_hooks_token,
    chatbase_token=chatbase_token,
    name="TradingNewsBot",
    proxy=proxy_string,
)

manager = None


async def init(host):
    global manager

    redis: Redis = await create_redis_pool(host, minsize=5, maxsize=10)
    manager = Manager(redis=redis)

    async for chat_id, data in manager.check_new_all(save=False):
        pass

    return bot, manager


@bot.command(r"/start")
async def start(chat: Chat, match):
    user = chat.message["from"]
    manager.start(user["id"], user.get("username"))
    await key(chat, match)


@bot.command(r"/stop")
async def stop(chat: Chat, match):
    manager.stop(chat.id)
    await key(chat, match)


@bot.command(r"^About$")
@bot.command(r"/about")
async def about(chat: Chat, _=None):
    await chat.send_text(
        "Привет. Я бот для оповещения. Не обижайте меня, я буду верно вам служить. \n"
        "Умею подписываться на пользователей и темы на форуме mfd.ru и оповещать о новых сообщениях\n"
        "Могу сообщить, когда появляется новая тема или новость на Алёнке. \n"
        "Пользуйтесь на здоровье!"
    )


# Начальная настройка клавиатуры
@bot.command(r"^Отмена$")
@bot.command(r"/key")
async def key(chat: Chat, _=None):
    options = ["Подписки", "About"]
    reply_markup = build_menu(
        options, n_cols=2, header_buttons=["Смартлаб топ 24 часа"]
    )
    await chat.send_text("Hey!", reply_markup=reply_markup)


@bot.command(r"^Смартлаб топ 24 часа$")
async def smartlab(chat: Chat, _=None):
    sl = SmartLab()
    posts = await sl.check_update()
    await chat.send_text(
        posts.posts[0].format(),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


@bot.command(r"^Подписки$")
async def settings(chat: Chat, _=None):
    user_id = chat.id
    manager.set_state(user_id, State.IDLE)

    if manager.settings(user_id).alenka:
        alenka = "Отписаться от ALЁNKA"
    else:
        alenka = "Подписаться на ALЁNKA"

    options = [alenka, "MFD.ru тема", "MFD.ru пользователи"]
    await chat.send_text(
        "Управление подписками",
        reply_markup=keyboard_markup(options, ["Текущие подписки"], 3),
    )


@bot.command(r"^Текущие подписки$")
async def print_settings(chat: Chat, _=None):
    current_settings = manager.settings(chat.id)
    msg = ""

    if (
        current_settings.alenka
        or len(current_settings.mfd_user) > 0
        or len(current_settings.mfd_thread) > 0
    ):
        msg += "Вы подписаны на:\n"
    else:
        await chat.send_text(
            "У вас нет активных подписок.", parse_mode="Markdown"
        )
        return

    if current_settings.alenka:
        msg += "  Новости с [https://alenka.capital](alenka.capital)\n\n"

    msg += fill_mfd_user(current_settings)
    msg += "\n"
    msg += fill_mfd_thread(current_settings)

    await chat.send_text(msg, parse_mode="Markdown")


def fill_mfd_user(current_settings):
    if len(current_settings.mfd_user) == 1:
        for user in current_settings.mfd_user:
            return f"  Пользователя [{user.name}](http://forum.mfd.ru/forum/poster/?id={user.id})\n"
    elif len(current_settings.mfd_user) > 1:
        msg = "  На пользователей: \n"
        for user in current_settings.mfd_user:
            msg += f"    [{user.name}](http://forum.mfd.ru/forum/poster/?id={user.id})\n"
        return msg
    return ""


def fill_mfd_thread(current_settings):
    if len(current_settings.mfd_thread) == 1:
        for thread in current_settings.mfd_thread:
            return f"  Тему [{thread.name}](http://forum.mfd.ru/forum/thread/?id={thread.id})\n"
    elif len(current_settings.mfd_thread) > 1:
        msg = f"  На темы: \n"
        for thread in current_settings.mfd_thread:
            msg += f"    [{thread.name}](http://forum.mfd.ru/forum/thread/?id={thread.id})\n"
        return msg
    return ""


@bot.command(r"^Подписаться на ALЁNKA$")
async def subscribe_alenka(chat: Chat, match):
    text, _ = await manager.new_command(chat.id, Manager.ADD_ALENKA)
    await chat.send_text(text)
    await settings(chat, match)


@bot.command(r"^Отписаться от ALЁNKA$")
async def unsubscribe_alenka(chat: Chat, match):
    text, _ = await manager.new_command(chat.id, Manager.REMOVE_ALENKA)
    await chat.send_text(text)
    await settings(chat, match)


@bot.command(r"^MFD.ru тема")
async def mfd_forum(chat: Chat, _=None):
    options = ["Добавить mfd тему", "Удалить mfd тему"]
    await chat.send_text(
        "Выберете действие: ", reply_markup=keyboard_markup(options)
    )


@bot.command(r"^Добавить mfd тему$")
async def mfd_forum_add(chat: Chat, _=None):
    await chat.send_text(
        "Введите имя темы или ссылку на тему или любое сообщение этой темы ",
        reply_markup=keyboard_markup(),
    )
    manager.set_state(chat.id, State.MFD_THREAD_ADD)


@bot.command(r"^Удалить mfd тему$")
async def mfd_forum_remove(chat: Chat, _=None):
    chat_id = chat.id
    await chat.send_text(
        "Выберете тему для удаления: ",
        reply_markup=keyboard_markup(
            [data.name for data in manager.settings(chat_id).mfd_thread],
            n_col=1,
        ),
    )
    manager.set_state(chat.id, State.MFD_THREAD_REMOVE)


@bot.command(r"^MFD.ru пользователи")
async def mfd_user(chat: Chat, _=None):
    options = ["Добавить mfd пользователя", "Удалить mfd пользователя"]
    await chat.send_text(
        "Выберете действие: ", reply_markup=keyboard_markup(options)
    )


@bot.command(r"^Добавить mfd пользователя$")
async def mfd_user_add(chat: Chat, _=None):
    await chat.send_text(
        'Введите имя темы или ссылку на пользователя.\nЕсли передумали, введите "Отмена" ',
        reply_markup=keyboard_markup(),
    )
    manager.set_state(chat.id, State.MFD_USER_ADD)


@bot.command(r"^Удалить mfd пользователя$")
async def mfd_user_remove(chat: Chat, _=None):
    await chat.send_text(
        "Выберете пользователя для удаления: ",
        reply_markup=keyboard_markup(
            [data.name for data in manager.settings(chat.id).mfd_user], n_col=1
        ),
    )
    manager.set_state(chat.id, State.MFD_USER_REMOVE)


@bot.default
async def received_information(chat: Chat, _=None):
    st = manager.state(chat.id)
    if st == State.IDLE:
        return
    if st == State.MFD_THREAD_ADD:
        await mfd_add_thread(chat)
    if st == State.MFD_THREAD_REMOVE:
        await mfd_remove_thread(chat)
    if st == State.MFD_USER_ADD:
        await mfd_add_user(chat)
    if st == State.MFD_USER_REMOVE:
        await mfd_remove_user(chat)


async def mfd_remove_user(chat: Chat):
    text = str(chat.message["text"])
    res = ""
    for data in manager.settings(chat.id).mfd_user:
        if data.name == text:
            res, _ = await manager.new_command(
                chat.id, Manager.REMOVE_MFD_USER, data
            )
    if res:
        await chat.send_text(res)
        await settings(chat)
    else:
        await chat.send_text(
            "Данный пользователь не найден для удаления. Введите правильное имя"
        )


async def mfd_remove_thread(chat: Chat):
    text = str(chat.message["text"])
    res = ""
    for data in manager.settings(chat.id).mfd_thread:
        if data.name == text:
            res, _ = await manager.new_command(
                chat.id, Manager.REMOVE_MFD_THREAD, data
            )

    if res:
        await chat.send_text(res)
        await settings(chat)
    else:
        await chat.send_text(
            "Данная тема не найдена для удаления. Попробуйте еще раз"
        )


async def mfd_add_user(chat: Chat):
    text = str(chat.message["text"])
    rating = -1
    if ": " in text:
        try:
            spl = text.split(":")
            text = str(spl[0]).strip()
            rating = int(spl[1])
        except Exception:
            rating = 0

    cid = chat.id
    if text.startswith("http"):
        answer = await manager.resolve_mfd_user_link(cid, text)
        if not answer:
            await chat.send_text(f"Пользователь {answer} добавлен в подписки")
            await settings(chat)
        else:
            await chat.send_text(
                "Пользователь не найден. Проверьте ссылку и попробуйте еще раз"
            )
    else:
        await chat.send_chat_action("typing")
        users, res = await manager.find_mfd_user(cid, text, rating)
        if len(users) == 1:
            await chat.send_text(res)
            await settings(chat)
        if len(users) > 1:
            await chat.send_text(
                "Найдено несколько пользователей. Уточните запрос или введите новый. Имя: Рейтинг",
                reply_markup=keyboard_markup(
                    [f"{user[1]} : {user[3]}" for user in users], n_col=1
                ),
            )
        if len(users) == 0:
            await chat.send_text("Пользователь не найден. Введите новый запрос")


async def mfd_add_thread(chat: Chat):
    text = str(chat.message["text"])
    cid = chat.id

    if text.startswith("http"):
        answer = await manager.resolve_mfd_thread_link(cid, text)
        if answer is not None:
            await chat.send_text(f"Тема {answer} добавлена в подписки")
            await settings(chat)
        else:
            await chat.send_text(
                "Тема не найдена. Проверьте ссылку и попробуйте еще раз"
            )
    else:
        await chat.send_chat_action("typing")
        titles, res = await manager.find_mfd_thread(cid, text)
        if len(titles) == 1:
            await chat.send_text(res)
            await settings(chat)
        if len(titles) > 1:
            await chat.send_text(
                "Найдено несколько тем. Уточните запрос или введите новый",
                reply_markup=keyboard_markup(titles, n_col=1),
            )
        if len(titles) == 0:
            await chat.send_text(
                "Тема с таким именем не найдена. Введите новый запрос"
            )
