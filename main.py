import asyncio
import os
import re
import time
import sqlite3
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.account import GetAuthorizationsRequest
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights

API_ID = 33291160
API_HASH = "a19e7fa3783e6e282b70e7fa2969302c"
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
taglocks = {}  # {chat_id: target_msg_id}

# ================= KEEP-ALIVE SERVER =================
async def handle_ping(request):
    return web.Response(text="Multi-Userbot Host is Live!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# Helper to get target user
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

# ================= USERBOT COMMAND HANDLERS =================
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
        help_text = (
            "❁═══⟬ GCTOOLS & TAGLOCK ⟭═══❁\n"
            "⟡➣ `.ban`: Ban a user\n"
            "⟡➣ `.unban`: Unban user\n"
            "⟡➣ `.mute`: Mute user in group\n"
            "⟡➣ `.unmute`: Unmute user\n"
            "⟡➣ `.kick`: Kick user from group\n"
            "⟡➣ `.purge`: Delete replied msg to latest\n"
            "⟡➣ `.purgeme <N>`: Delete your last N msgs\n"
            "⟡➣ `.spurge <keyword>`: Delete msgs matching keyword\n"
            "⟡➣ `.delall`: Delete all msgs from replied user\n"
            "⟡➣ `.editpurge`: Stealth purge (edit to '.')\n"
            "⟡➣ `.lockgc / .unlockgc`: Lock/Unlock group\n"
            "⟡➣ `.locked`: Show all active locks\n"
            "⟡➣ `.pin / .unpin / .unpinall`: Pin/unpin msgs\n"
            "⟡➣ `.check`: Check stats/info\n"
            "⟡➣ `.admins`: Check all group admins\n"
            "⟡➣ `.zombies` / `.zombies remove`: Scan/kick deleted accounts\n"
            "⟡➣ `.taglock` / `.taglock <msg_link>`: Auto taglock all msgs to a msg\n"
            "⟡➣ `.untaglock`: Stop active taglock\n"
            "⟡➣ `/devices`: Sessions list (Owner only)\n"
            "❁════════════════════❁"
        )
        await event.edit(help_text)

    # Restrict /devices strictly to OWNER_ID
    @client.on(events.NewMessage(outgoing=True, pattern=r"^/(?:connect|devices|sessions)$"))
    async def list_connected_devices(event):
        me = await event.client.get_me()
        if me.id != OWNER_ID:
            return await event.edit("⛔ **Access Denied:** Sirf bot owner ke liye authorized hai.")

        msg = await event.edit("🔍 **Fetching active sessions...**")
        try:
            authorizations = await event.client(GetAuthorizationsRequest())
            text = f"📱 **Active Sessions:** `{len(authorizations.authorizations)}`\n\n"
            for idx, auth in enumerate(authorizations.authorizations, 1):
                cur = " *(Current)*" if auth.current else ""
                text += f"**{idx}.** `{auth.device_model}` ({auth.platform}){cur}\n"
                text += f"   📍 IP: `{auth.ip}` | {auth.country}\n"
            await msg.edit(text)
        except Exception as e:
            await msg.edit(f"❌ Failed: `{e}`")

    # ================= TAGLOCK HANDLERS =================
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.taglock(?:\s+(.+))?$"))
    async def taglock_cmd(event):
        arg = (event.pattern_match.group(1) or "").strip()
        chat_id = event.chat_id

        if arg.lower() == "status":
            if chat_id in taglocks:
                return await event.edit(f"🔒 **Taglock is ACTIVE on Message ID:** `{taglocks[chat_id]}`")
            return await event.edit("🔓 **Taglock is NOT active in this chat.**")

        target_msg_id = None

        if arg:
            # Match Telegram message link (public or private c/ links)
            link_match = re.search(r"t\.me/(?:c/)?([^/]+)/(\d+)", arg)
            if link_match:
                target_msg_id = int(link_match.group(2))
            elif arg.isdigit():
                target_msg_id = int(arg)

        if not target_msg_id and event.is_reply:
            rep = await event.get_reply_message()
            target_msg_id = rep.id

        if not target_msg_id:
            return await event.edit("❌ **Usage:**\n1. Reply to a message with `.taglock`\n2. Or send `.taglock <msg_link>`")

        taglocks[chat_id] = target_msg_id
        await event.edit(f"🎯 **Taglock Activated!**\nAb is group ke har message par Message ID `{target_msg_id}` reply/tag hoga.")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.untaglock$"))
    async def untaglock_cmd(event):
        if event.chat_id in taglocks:
            taglocks.pop(event.chat_id, None)
            await event.edit("🔓 **Taglock Disabled successfully for this chat.**")
        else:
            await event.edit("❌ **No active taglock found in this chat.**")

    # Auto tag listener
    @client.on(events.NewMessage)
    async def auto_taglock_listener(event):
        if event.chat_id not in taglocks:
            return
        # Ignore userbot's own control commands
        if event.text and event.text.startswith((".taglock", ".untaglock", ".ping", ".alive")):
            return
        target_id = taglocks[event.chat_id]
        if event.id == target_id:
            return
        try:
            # Agar incoming message already kisi aur ko reply nahi kar raha, toh taglock target ko reply mention karega
            if not event.reply_to_msg_id:
                await event.reply("📍", reply_to=target_id)
        except Exception:
            pass

    # ================= GCTOOLS HANDLERS =================
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ban(?:\s+(.*))?$"))
    async def ban_cmd(event):
        uid = await get_target(event)
        if not uid:
            return await event.edit("❌ Reply to a user or provide username/ID.")
        try:
            await event.client(EditBannedRequest(event.chat_id, uid, ChatBannedRights(until_date=None, view_messages=True)))
            await event.edit(f"🚫 **Banned:** `{uid}`")
        except Exception as e:
            await event.edit(f"❌ Failed: `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.unban(?:\s+(.*))?$"))
    async def unban_cmd(event):
        uid = await get_target(event)
        if not uid:
            return await event.edit("❌ Reply to a user or provide username/ID.")
        try:
            await event.client(EditBannedRequest(event.chat_id, uid, ChatBannedRights(until_date=None)))
            await event.edit(f"✅ **Unbanned:** `{uid}`")
        except Exception as e:
            await event.edit(f"❌ Failed: `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.mute(?:\s+(.*))?$"))
    async def mute_cmd(event):
        uid = await get_target(event)
        if not uid:
            return await event.edit("❌ Reply to a user or provide username/ID.")
        try:
            await event.client(EditBannedRequest(event.chat_id, uid, ChatBannedRights(until_date=None, send_messages=True)))
            await event.edit(f"🔇 **Muted:** `{uid}`")
        except Exception as e:
            await event.edit(f"❌ Failed: `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.unmute(?:\s+(.*))?$"))
    async def unmute_cmd(event):
        uid = await get_target(event)
        if not uid:
            return await event.edit("❌ Reply to a user or provide username/ID.")
        try:
            await event.client(EditBannedRequest(event.chat_id, uid, ChatBannedRights(until_date=None, send_messages=False)))
            await event.edit(f"🔊 **Unmuted:** `{uid}`")
        except Exception as e:
            await event.edit(f"❌ Failed: `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.kick(?:\s+(.*))?$"))
    async def kick_cmd(event):
        uid = await get_target(event)
        if not uid:
            return await event.edit("❌ Reply to a user or provide username/ID.")
        try:
            await event.client.kick_participant(event.chat_id, uid)
            await event.edit(f"👢 **Kicked:** `{uid}`")
        except Exception as e:
            await event.edit(f"❌ Failed: `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.purge$"))
    async def purge_cmd(event):
        if not event.is_reply:
            return await event.edit("❌ Reply to a message to purge from.")
        rep = await event.get_reply_message()
        msgs = []
        async for m in event.client.iter_messages(event.chat_id, min_id=rep.id - 1):
            msgs.append(m.id)
            if len(msgs) >= 100:
                await event.client.delete_messages(event.chat_id, msgs)
                msgs = []
        if msgs:
            await event.client.delete_messages(event.chat_id, msgs)
        temp = await event.respond("🧹 **Purged successfully!**")
        await asyncio.sleep(2)
        await temp.delete()

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.purgeme\s+(\d+)$"))
    async def purgeme_cmd(event):
        count = int(event.pattern_match.group(1))
        me = await event.client.get_me()
        msgs = []
        async for m in event.client.iter_messages(event.chat_id, from_user=me.id):
            msgs.append(m.id)
            if len(msgs) >= count:
                break
        await event.client.delete_messages(event.chat_id, msgs)
        temp = await event.respond(f"🧹 Purged `{len(msgs)}` of your messages.")
        await asyncio.sleep(2)
        await temp.delete()

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.spurge\s+(.+)$"))
    async def spurge_cmd(event):
        kw = event.pattern_match.group(1).lower()
        msgs = []
        async for m in event.client.iter_messages(event.chat_id, limit=100):
            if m.text and kw in m.text.lower():
                msgs.append(m.id)
        if msgs:
            await event.client.delete_messages(event.chat_id, msgs)
        temp = await event.respond(f"🧹 Purged `{len(msgs)}` messages matching keyword.")
        await asyncio.sleep(2)
        await temp.delete()

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.delall$"))
    async def delall_cmd(event):
        uid = await get_target(event)
        if not uid:
            return await event.edit("❌ Reply to a user to delete their messages.")
        msgs = []
        async for m in event.client.iter_messages(event.chat_id, from_user=uid, limit=100):
            msgs.append(m.id)
        if msgs:
            await event.client.delete_messages(event.chat_id, msgs)
        temp = await event.respond(f"🧹 Deleted `{len(msgs)}` messages from user `{uid}`.")
        await asyncio.sleep(2)
        await temp.delete()

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.editpurge$"))
    async def editpurge_cmd(event):
        me = await event.client.get_me()
        async for m in event.client.iter_messages(event.chat_id, from_user=me.id, limit=20):
            try:
                await m.edit(".")
            except Exception:
                pass
        temp = await event.respond("🤫 **Stealth purge done.**")
        await asyncio.sleep(2)
        await temp.delete()

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.lockgc(?:\s+(.+))?$"))
    async def lockgc_cmd(event):
        gc_locks[event.chat_id] = True
        await event.edit("🔒 **Group locked successfully!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.unlockgc(?:\s+(.+))?$"))
    async def unlockgc_cmd(event):
        gc_locks.pop(event.chat_id, None)
        await event.edit("🔓 **Group unlocked successfully!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.locked$"))
    async def locked_cmd(event):
        is_locked = gc_locks.get(event.chat_id, False)
        status = "🔒 Locked" if is_locked else "🔓 Unlocked"
        await event.edit(f"📊 **Current Chat Lock Status:** `{status}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.pin$"))
    async def pin_cmd(event):
        if not event.is_reply:
            return await event.edit("❌ Reply to a message to pin it.")
        rep = await event.get_reply_message()
        await event.client.pin_message(event.chat_id, rep.id, notify=False)
        await event.edit("📌 **Pinned successfully!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.unpin$"))
    async def unpin_cmd(event):
        if not event.is_reply:
            return await event.edit("❌ Reply to a message to unpin it.")
        rep = await event.get_reply_message()
        await event.client.unpin_message(event.chat_id, rep.id)
        await event.edit("📌 **Unpinned successfully!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.unpinall$"))
    async def unpinall_cmd(event):
        await event.client.unpin_message(event.chat_id)
        await event.edit("📌 **All messages unpinned!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.check$"))
    async def check_cmd(event):
        chat = await event.get_chat()
        await event.edit(f"ℹ️ **Chat Info:**\n📌 Title: `{chat.title}`\n🆔 Chat ID: `{chat.id}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.admins$"))
    async def admins_cmd(event):
        admins = await event.client.get_participants(event.chat_id, filter=events.ChannelParticipantsAdmins)
        text = f"👮‍♂️ **Admins in {event.chat.title} ({len(admins)}):**\n\n"
        for a in admins:
            text += f"• `{a.first_name}` (`{a.id}`)\n"
        await event.edit(text)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.zombies(?:\s+(remove))?$"))
    async def zombies_cmd(event):
        remove = (event.pattern_match.group(1) or "").lower() == "remove"
        msg = await event.edit("🧟 **Scanning for zombies (deleted accounts)...**")
        zombies = 0
        async for u in event.client.iter_participants(event.chat_id):
            if u.deleted:
                zombies += 1
                if remove:
                    try:
                        await event.client.kick_participant(event.chat_id, u.id)
                    except Exception:
                        pass
        if remove:
            await msg.edit(f"🧟 Cleaned `{zombies}` zombies (deleted accounts).")
        else:
            await msg.edit(f"🧟 Found `{zombies}` deleted accounts. Use `.zombies remove` to kick.")

# ================= ASSISTANT BOT HANDLERS =================
def register_bot_handlers(bot: TelegramClient):
    @bot.on(events.NewMessage(pattern=r"^/start$"))
    async def bot_start(event):
        await event.reply("👋 **Welcome to Multi-Userbot Host!**\nSend `/login` to start your userbot.")

    @bot.on(events.NewMessage(pattern=r"^/menu$"))
    async def bot_menu(event):
        await event.reply(
            "📋 **Available Commands:**\n"
            "• `/start` - Start host bot\n"
            "• `/login` - Host/Login a new userbot\n"
            "• `/status` - Check current connection"
        )

    @bot.on(events.NewMessage(pattern=r"^/status$"))
    async def bot_status(event):
        uid = event.sender_id
        if uid in active_clients:
            await event.reply("✅ Aapka userbot active chal raha hai!")
        else:
            await event.reply("❌ Aapka userbot connected nahi hai. `/login` bhejein.")

    @bot.on(events.NewMessage(pattern=r"^/login$"))
    async def login_handler(event):
        uid = event.sender_id
        if uid in active_clients:
            return await event.reply("✅ Userbot pehle se active chal raha hai!")

        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        login_states[uid] = {"step": "phone", "client": client}
        await event.reply("📱 Apna Phone Number country code ke sath bhejein (e.g., `+919876543210`):")

    @bot.on(events.NewMessage)
    async def process_login(event):
        if event.text.startswith("/") or not event.is_private:
            return
        uid = event.sender_id
        state = login_states.get(uid)
        if not state:
            return

        cl = state["client"]

        if state["step"] == "phone":
            phone = event.text.strip().replace(" ", "")
            state["phone"] = phone
            try:
                code_hash = await cl.send_code_request(phone)
                state["hash"] = code_hash
                state["step"] = "code"
                await event.reply("📩 Telegram login code bhejein (digits ke beech space dalein, e.g. `1 2 3 4 5`):")
            except Exception as e:
                login_states.pop(uid, None)
                await event.reply(f"❌ Error: {e}")

        elif state["step"] == "code":
            otp = event.text.strip().replace(" ", "")
            try:
                await cl.sign_in(state["phone"], otp, phone_code_hash=state["hash"].phone_code_hash)
                sess = cl.session.save()
                cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, 1)", (uid, sess))
                conn.commit()
                register_userbot_handlers(cl)
                active_clients[uid] = cl
                asyncio.create_task(cl.run_until_disconnected())
                login_states.pop(uid, None)
                await event.reply("🎉 Login Successful! Userbot started.\nApne account se `.ping` ya `.help` check karein.")
            except SessionPasswordNeededError:
                state["step"] = "2fa"
                await event.reply("🔐 2-Step Verification Password dalein:")
            except Exception as e:
                login_states.pop(uid, None)
                await event.reply(f"❌ Login failed: {e}")

        elif state["step"] == "2fa":
            try:
                await cl.sign_in(password=event.text.strip())
                sess = cl.session.save()
                cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, 1)", (uid, sess))
                conn.commit()
                register_userbot_handlers(cl)
                active_clients[uid] = cl
                asyncio.create_task(cl.run_until_disconnected())
                login_states.pop(uid, None)
                await event.reply("🎉 Login Successful! Userbot started.\nApne account se `.ping` ya `.help` check karein.")
            except Exception as e:
                login_states.pop(uid, None)
                await event.reply(f"❌ Password error: {e}")

# ================= RUNNER =================
async def main():
    await start_web_server()

    # Preload from STRING_SESSION env if present
    session_env = os.environ.get("STRING_SESSION") or ""
    if session_env:
        try:
            u_cl = TelegramClient(StringSession(session_env.strip()), API_ID, API_HASH)
            await u_cl.start()
            register_userbot_handlers(u_cl)
            me = await u_cl.get_me()
            active_clients[me.id] = u_cl
            asyncio.create_task(u_cl.run_until_disconnected())
        except Exception:
            pass

    # Load users from database
    cursor.execute("SELECT user_id, session_str FROM users WHERE is_active=1")
    for uid, sess in cursor.fetchall():
        if uid not in active_clients:
            try:
                u_cl = TelegramClient(StringSession(sess), API_ID, API_HASH)
                await u_cl.start()
                register_userbot_handlers(u_cl)
                active_clients[uid] = u_cl
                asyncio.create_task(u_cl.run_until_disconnected())
            except Exception:
                pass

    if BOT_TOKEN:
        bot = TelegramClient('bot_session', API_ID, API_HASH)
        await bot.start(bot_token=BOT_TOKEN)
        register_bot_handlers(bot)
        await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
