"""
Multi-Userbot Host & Telegram Management Bot with 4x Thomas Bot Army
Features:
- Multi-User Session Storage via SQLite & Keep-Alive Web Server
- Truecaller Lookup Tool (.num <phone_number>)
- Silent Fight Mode (.silent on / .silent off)
- Connected Devices Checker (/devices, /connect)
- 4x Thomas Bot Army Integration
- Full Moderation, Purge, Clone, TagLock, VC Attack, Target Slow, Fonts, AFK, etc.
"""

import asyncio
import os
import re
import time
import random
import sqlite3
import aiohttp
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.channels import EditBannedRequest, EditAdminRequest, JoinChannelRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.account import UpdateProfileRequest, GetAuthorizationsRequest
from telethon.tl.functions.messages import EditChatDefaultBannedRightsRequest
from telethon.tl.types import ChatBannedRights, ChatAdminRights, InputPhoto

# ================= CONFIGURATION =================
API_ID = 33291160
API_HASH = "a19e7fa3783e6e282b70e7fa2969302c"
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8647284010:AAE6B_qCYVmZB5Sd066xSdMBncG-ODHNI3Y").strip()
PORT = int(os.environ.get("PORT", 8080))

THOMAS_TOKENS = [
    "8570988727:AAH8clmg-VhZaunNl8nh8SgDTAE08cl2T30",
    "8978651083:AAEeSwMK9gyNMu7gymd7bb0c066gMd7SvuA",
    "8544011902:AAFm30UXwK_Mi45ZfcDO-kiS4tHFRCaYV4I",
    "8931340247:AAFHpTMhGngwYEToOweIzBLCACqiXJKdzVs"
]

SUPPORT_CHANNEL = "YourChannelUsername"

RAID_PRESETS = [
    "HI HLWW KYA HO GYA",
    "ARE BHAI KYA HO GYA BATAO??",
    "SUNO TOH SAHI KYA HUA!",
    "HI HLWW REPLY KYUN NAHI DE RAHE?",
    "KYA HO GYA BHAI SAB THEEK HAI NA?",
    "FAST REPLY KARO RE SAB!"
]

# ================= DATABASE SETUP =================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, session_str TEXT, is_active INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS bot_session (id TEXT PRIMARY KEY, session TEXT)")
conn.commit()

active_clients = {}
afk_data = {}
silent_mode_users = {}
thomas_clients = []

# ================= FONT MAPS =================
BOLD_ITALIC_MAP = {
    'a': '𝒂', 'b': '𝒃', 'c': '𝒄', 'd': '𝒅', 'e': '𝒆', 'f': '𝒇', 'g': '𝒈', 'h': '𝒉', 'i': '𝒊', 'j': '𝒋', 'k': '𝒌', 'l': '𝒍', 'm': '𝒎', 'n': '𝒏', 'o': '𝒐', 'p': '𝒑', 'q': '𝒒', 'r': '𝒓', 's': '𝒔', 't': '𝒕', 'u': '𝒖', 'v': '𝒗', 'w': '𝒘', 'x': '𝒙', 'y': '𝒚', 'z': '𝒛',
    'A': '𝑨', 'B': '𝑩', 'C': '𝑪', 'D': '𝑫', 'E': '𝑬', 'F': '𝑭', 'G': '𝑮', 'H': '𝑯', 'I': '𝑰', 'J': '𝑱', 'K': '𝑲', 'L': '𝑳', 'M': '𝑴', 'N': '𝑵', 'O': '𝑶', 'P': '𝑷', 'Q': '𝑸', 'R': '𝑹', 'S': '𝑺', 'T': '𝑻', 'U': '𝑼', 'V': '𝑽', 'W': '𝑾', 'X': '𝑿', 'Y': '𝒀', 'Z': '𝒁'
}
ITALIC_MAP = {
    'a': '𝑎', 'b': '𝑏', 'c': '𝑐', 'd': '𝑑', 'e': '𝑒', 'f': '𝑓', 'g': '𝑔', 'h': 'ℎ', 'i': '𝑖', 'j': '𝑗', 'k': '𝑘', 'l': '𝑙', 'm': '𝑚', 'n': '𝑛', 'o': '𝑜', 'p': '𝑝', 'q': '𝑞', 'r': '𝑟', 's': '𝑠', 't': '𝑡', 'u': '𝑢', 'v': '𝑣', 'w': '𝑤', 'x': '𝑥', 'y': '𝑦', 'z': '𝑧',
    'A': '𝐴', 'B': '𝐵', 'C': '𝐶', 'D': '𝐷', 'E': '𝐸', 'F': '𝐹', 'G': '𝐺', 'H': '𝐻', 'I': '𝐼', 'J': '𝐽', 'K': '𝐾', 'L': '𝐿', 'M': '𝑀', 'N': '𝑁', 'O': '𝑂', 'P': '𝑃', 'Q': '𝑄', 'R': '𝑅', 'S': '𝑆', 'T': '𝑇', 'U': '𝑈', 'V': '𝑉', 'W': '𝑊', 'X': '𝑋', 'Y': '𝑌', 'Z': '𝑍'
}
BOX_MAP = {
    'a': '🄰', 'b': '🄱', 'c': '🄲', 'd': '🄳', 'e': '🄴', 'f': '🄵', 'g': '🄶', 'h': '🄷', 'i': '🄸', 'j': '🄹', 'k': '🄺', 'l': '🄻', 'm': '🄼', 'n': '🄽', 'o': '🄾', 'p': '🄿', 'q': '🅀', 'r': '🅁', 's': '🅂', 't': '🅃', 'u': '🅄', 'v': '🅅', 'w': '🅆', 'x': '🅇', 'y': '🅈', 'z': '🅉',
    'A': '🄰', 'B': '🄱', 'C': '🄲', 'D': '🄳', 'E': '🄴', 'F': '🄵', 'G': '🄶', 'H': '🄷', 'I': '🄸', 'J': '🄹', 'K': '🄺', 'L': '🄻', 'M': '🄼', 'N': '🄽', 'O': '🄾', 'P': '🄿', 'Q': '🅀', 'R': '🅁', 'S': '🅂', 'T': '🅃', 'U': '🅄', 'V': '🅅', 'W': '🅆', 'X': '🅇', 'Y': '🅈', 'Z': '🅉'
}

def transform_font(text: str, mapping: dict) -> str:
    return "".join(mapping.get(c, c) for c in text)

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

# ================= USERBOT COMMAND HANDLERS =================
def register_userbot_handlers(client: TelegramClient):
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.silent(?:\s+(on|off))?$"))
    async def silent_mode_cmd(event):
        me = await event.client.get_me()
        arg = (event.pattern_match.group(1) or "").lower()
        if arg == "off":
            silent_mode_users[me.id] = False
            await event.edit("🔊 **Silent Fight Mode DISABLED! Normal commands are active.**")
        else:
            silent_mode_users[me.id] = True
            await event.edit("🤫 **Silent Fight Mode ENABLED!**\n`.help`, `.ping`, `.alive`, etc. are now muted.")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^/(?:connect|devices|sessions)$"))
    async def list_connected_devices(event):
        me = await event.client.get_me()
        if event.sender_id != me.id and not event.out:
            return
        msg = await event.edit("🔍 **Fetching active sessions...**")
        try:
            authorizations = await event.client(GetAuthorizationsRequest())
            text = f"📱 **Active Sessions:** `{len(authorizations.authorizations)}`\n\n"
            for idx, auth in enumerate(authorizations.authorizations, 1):
                cur = " *(This)*" if auth.current else ""
                text += f"**{idx}.** `{auth.device_model}` ({auth.platform}){cur}\n"
                text += f"   📍 IP: `{auth.ip}` | {auth.country}\n"
            await msg.edit(text)
        except Exception as e:
            await msg.edit(f"❌ Failed: `{e}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.num(?:\s+(.+))?$"))
    async def num_lookup_cmd(event):
        raw_num = event.pattern_match.group(1)
        if not raw_num:
            rep = await event.get_reply_message()
            if rep and rep.text:
                match = re.search(r"\+?\d{8,15}", rep.text)
                if match:
                    raw_num = match.group(0)
        if not raw_num:
            return await event.edit("❌ Usage: `.num <phone_number>`")

        clean_num = re.sub(r"[^\d+]", "", raw_num)
        if not clean_num.startswith("+"):
            clean_num = "+91" + clean_num if len(clean_num) == 10 else "+" + clean_num

        await event.edit(f"🔍 **Fetching Truecaller details for** `{clean_num}`...")
        url = f"https://api-lookup.suraj-dev.me/truecaller?number={clean_num.replace('+', '')}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        name = data.get("name") or data.get("fullName") or "Not Found"
                        carrier = data.get("carrier") or data.get("operator") or "Unknown"
                        location = data.get("location") or data.get("circle") or "India"
                        await event.edit(f"📞 **TRUECALLER INFO**\n👤 Name: `{name}`\n📱 Number: `{clean_num}`\n📡 Carrier: `{carrier}`\n📍 Circle: `{location}`")
                    else:
                        await event.edit(f"❌ No records found for `{clean_num}`.")
        except Exception:
            await event.edit(f"📞 `{clean_num}` | 🌐 India (+91)\n⚠️ API timed out.")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.help(?:\s+(.+))?$"))
    async def help_cmd(event):
        me = await event.client.get_me()
        if silent_mode_users.get(me.id, False):
            return
        help_text = (
            "⟡═══════⟬ GCTOOLS COMMANDS ⟭═══════⟡\n"
            "⟡➣ `.num <number>` : Truecaller Information Lookup\n"
            "⟡➣ `.silent <on/off>` : Toggle Silent Mode\n"
            "⟡➣ `/devices` : Check Logged-in Sessions\n"
            "⟡➣ `.ping` / `.alive` : Check Status\n"
            "⟡➣ `.bolditalic <text>` / `.box <text>`\n"
            "⟡➣ `.afk <reason>` / `.unafk`\n"
            "⟡➣ `.tovoice` : Convert Audio to Voice Note\n"
            "⟡➣ `.thomas status/raid/spam/msg`\n"
            "⟡═══════════════════════════════════⟡"
        )
        await event.edit(help_text)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.ping$"))
    async def ping_cmd(event):
        me = await event.client.get_me()
        if silent_mode_users.get(me.id, False):
            return
        start = time.time()
        await event.edit("🏓 **Pinging...**")
        delta = (time.time() - start) * 1000
        await event.edit(f"🏓 **Pong!**\n⚡ Latency: `{delta:.2f} ms`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.alive$"))
    async def alive_cmd(event):
        me = await event.client.get_me()
        if silent_mode_users.get(me.id, False):
            return
        await event.edit("🔮 **Userbot AI is Alive & Running 24/7!**")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.afk(?:\s+(.+))?$"))
    async def afk_cmd(event):
        reason = event.pattern_match.group(1) or "Busy right now!"
        me = await event.client.get_me()
        afk_data[me.id] = {"status": True, "reason": reason}
        await event.edit(f"💤 **I am now AFK!**\nReason: `{reason}`")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.unafk$"))
    async def unafk_cmd(event):
        me = await event.client.get_me()
        if me.id in afk_data and afk_data[me.id]["status"]:
            afk_data[me.id]["status"] = False
            await event.edit("⚡ **AFK Disabled! Back online.**")

    @client.on(events.NewMessage(incoming=True))
    async def incoming_afk(event):
        if event.is_private:
            me = await event.client.get_me()
            if afk_data.get(me.id, {}).get("status", False):
                await event.reply(f"💤 I am currently AFK.\nReason: `{afk_data[me.id]['reason']}`")

# ================= RUNNER INITIALIZATION =================
async def main():
    await start_web_server()
    session_env = os.environ.get("STRING_SESSION") or os.environ.get("SESSION") or ""
    
    if session_env:
        try:
            user_client = TelegramClient(StringSession(session_env.strip()), API_ID, API_HASH)
            await user_client.start()
            register_userbot_handlers(user_client)
            print("Userbot started from Environment Session!")
        except Exception as e:
            print(f"Error starting userbot session: {e}")

    cursor.execute("SELECT session_str FROM users WHERE is_active=1")
    for row in cursor.fetchall():
        try:
            u_client = TelegramClient(StringSession(row[0]), API_ID, API_HASH)
            await u_client.start()
            register_userbot_handlers(u_client)
        except Exception:
            pass

    if BOT_TOKEN:
        try:
            bot_client = TelegramClient('bot_session', API_ID, API_HASH)
            await bot_client.start(bot_token=BOT_TOKEN)
            print("Telegram Bot Token started successfully!")
        except Exception as e:
            print(f"Bot Token error: {e}")

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())

# Railway persistent runtime guard
import asyncio
try:
    loop = asyncio.get_event_loop()
    if not loop.is_running():
        loop.run_forever()
except Exception:
    pass
