import asyncio
import os
import re
import time
import sqlite3
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import GetAuthorizationsRequest
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights

API_ID = int(os.environ.get("API_ID", 33291160))
API_HASH = os.environ.get("API_HASH", "a19e7fa3783e6e282b70e7fa2969302c").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8647284010:AAE6B_qCYVmZB5Sd066xSdMBncG-ODHNI3Y").strip()
PORT = int(os.environ.get("PORT", 8080))
OWNER_ID = 8225211569

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, session_str TEXT, is_active INTEGER)")
conn.commit()

active_clients = {}
login_states = {}
gc_locks = {}
taglocks = {}

# Keep-Alive Server
async def handle_ping(request):
    return web.Response(text="Multi-Userbot Host is Live!")

async def start_web_server():
    try:
        app = web.Application()
        app.router.add_get("/", handle_ping)
        app.router.add_get("/health", handle_ping)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        print(">> Web server started on port", PORT)
    except Exception as e:
        print(f">> Web server port bind skipped: {e}")

async def get_target(event):
    if event.is_reply:
        reply = await event.get_reply_message()
        return reply.sender_id
    args = event.text.split()
    if len(args) > 1:
        try:
            return int(args[1])
        except ValueError:
            user = await event.client.get_entity(args[1])
            return user.id
    return None

def register_userbot_handlers(client: TelegramClient):
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ping$"))
    async def ping_cmd(event):
        start = time.time()
        await event.edit("🏓 **Pinging...**")
        delta = (time.time() - start) * 1000
        await event.edit(f"🏓 **Pong!**\n⚡ Latency: `{delta:.2f} ms`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.alive$"))
    async def alive_cmd(event):
        await event.edit("🔮 **Thomas Multi-Userbot is Alive & Running 24/7!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^(?:\.help|/menu)$"))
    async def help_cmd(event):
        await event.edit(
            "❁═══⟬ GCTOOLS & TAGLOCK ⟭═══❁\n"
            "⟡➣ `.ping` / `.alive`\n"
            "⟡➣ `.ban` / `.unban` / `.mute` / `.unmute` / `.kick`\n"
            "⟡➣ `.purge` / `.purgeme <N>` / `.spurge <kw>` / `.delall`\n"
            "⟡➣ `.lockgc` / `.unlockgc` / `.locked`\n"
            "⟡➣ `.pin` / `.unpin` / `.unpinall`\n"
            "⟡➣ `.check` / `.admins` / `.zombies`\n"
            "⟡➣ `.taglock` / `.untaglock`\n"
            "⟡➣ `/devices` (Owner only)\n"
            "❁════════════════════❁"
        )

    @client.on(events.NewMessage(outgoing=True, pattern=r"^/(?:connect|devices|sessions)$"))
    async def list_connected_devices(event):
        me = await event.client.get_me()
        if me.id != OWNER_ID:
            return await event.edit("⛔ Access Denied.")
        try:
            authorizations = await event.client(GetAuthorizationsRequest())
            text = f"📱 **Active Sessions:** `{len(authorizations.authorizations)}`\n\n"
            for idx, auth in enumerate(authorizations.authorizations, 1):
                cur = " *(Current)*" if auth.current else ""
                text += f"**{idx}.** `{auth.device_model}` ({auth.platform}){cur}\n"
                text += f"   📍 IP: `{auth.ip}` | {auth.country}\n"
            await event.edit(text)
        except Exception as e:
            await event.edit(f"❌ Failed: `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.taglock(?:\s+(.+))?$"))
    async def taglock_cmd(event):
        arg = (event.pattern_match.group(1) or "").strip()
        chat_id = event.chat_id
        target_msg_id = None
        if arg:
            link_match = re.search(r"t\.me/(?:c/)?([^/]+)/(\d+)", arg)
            if link_match:
                target_msg_id = int(link_match.group(2))
            elif arg.isdigit():
                target_msg_id = int(arg)
        if not target_msg_id and event.is_reply:
            rep = await event.get_reply_message()
            target_msg_id = rep.id
        if not target_msg_id:
            return await event.edit("❌ Reply to a message with `.taglock` or provide link.")
        taglocks[chat_id] = target_msg_id
        await event.edit(f"🎯 **Taglock Activated on ID:** `{target_msg_id}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.untaglock$"))
    async def untaglock_cmd(event):
        taglocks.pop(event.chat_id, None)
        await event.edit("🔓 Taglock disabled.")

    @client.on(events.NewMessage)
    async def auto_taglock_listener(event):
        if event.chat_id not in taglocks:
            return
        if event.text and event.text.startswith((".taglock", ".untaglock", ".ping", ".alive")):
            return
        target_id = taglocks[event.chat_id]
        if event.id == target_id:
            return
        try:
            if not event.reply_to_msg_id:
                await event.reply("📍", reply_to=target_id)
        except Exception:
            pass

def register_bot_handlers(bot: TelegramClient):
    @bot.on(events.NewMessage(pattern=r"^/start$"))
    async def bot_start(event):
        await event.reply("👋 **Multi-Userbot Host is Live!**\nSend `/login` to connect your account.")

    @bot.on(events.NewMessage(pattern=r"^/status$"))
    async def bot_status(event):
        uid = event.sender_id
        if uid in active_clients:
            await event.reply("✅ Aapka userbot active chal raha hai!")
        else:
            await event.reply("❌ Userbot offline hai. Send `/login`.")

async def main():
    print(">> Starting host application...")
    await start_web_server()

    # Safe start String Session without interactive freeze
    session_env = os.environ.get("STRING_SESSION", "").strip()
    if session_env:
        print(">> Connecting STRING_SESSION...")
        try:
            u_cl = TelegramClient(StringSession(session_env), API_ID, API_HASH)
            await u_cl.connect()
            if await u_cl.is_user_authorized():
                register_userbot_handlers(u_cl)
                me = await u_cl.get_me()
                active_clients[me.id] = u_cl
                asyncio.create_task(u_cl.run_until_disconnected())
                print(f">> Userbot connected as {me.first_name} ({me.id})")
            else:
                print(">> STRING_SESSION is invalid/expired! Skipping interactive prompt.")
        except Exception as e:
            print(f">> Failed to load STRING_SESSION: {e}")

    # Start Bot Token client
    if BOT_TOKEN:
        print(">> Connecting Telegram Bot Token...")
        bot = TelegramClient('bot_session', API_ID, API_HASH)
        await bot.start(bot_token=BOT_TOKEN)
        register_bot_handlers(bot)
        bot_me = await bot.get_me()
        print(f">> Telegram Bot @{bot_me.username} is fully ONLINE and listening!")
        await bot.run_until_disconnected()
    else:
        print(">> No BOT_TOKEN found! Keep container alive.")
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
