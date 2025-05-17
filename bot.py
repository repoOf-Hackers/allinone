import os
import re
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Use environment variable
DOWNLOAD_DIR = 'downloads'
TELEGRAM_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
YOUTUBE_COOKIES_FILE = 'cookies.txt'  # File name used in Render secret

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*\u200b\u202c\u202d\u202e\u202f]', '', name)[:150]

def is_youtube_url(url):
    return "youtube.com" in url or "youtu.be" in url

def get_video_info(url: str):
    ydl_opts = {
        'quiet': True,
        'noplaylist': True,
    }

    if is_youtube_url(url):
        ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE

    with YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def download_media(url: str, is_audio: bool = False):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    info = get_video_info(url)
    title = sanitize_filename(info.get('title', 'media'))
    ext = 'mp3' if is_audio else info.get('ext', 'mp4')
    output_path = os.path.join(DOWNLOAD_DIR, f"{title}.{ext}")

    ydl_opts = {
        'format': 'bestaudio/best' if is_audio else 'best',
        'outtmpl': output_path,
        'noplaylist': True,
        'quiet': True,
        'postprocessors': [ {
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }] if is_audio else [],
    }

    if is_youtube_url(url):
        ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return output_path, info

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Send me a link from YouTube, Facebook, Instagram, etc.\n"
        "🟣 To get MP3 only, start your message with `audio` or `mp3`."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    is_audio = text.lower().startswith("mp3") or text.lower().startswith("audio")
    url_match = re.search(r'(https?://[^\s]+)', text)
    
    if not url_match:
        await update.message.reply_text("❗ Please send a valid media link.")
        return

    url = url_match.group(1)
    try:
        await update.message.reply_text("ℹ️ Fetching media info...")
        info = get_video_info(url)
        title = info.get('title', 'Unknown Title')
        duration = info.get('duration')
        msg = f"📌 *Title:* {title}"
        if duration:
            mins, secs = divmod(int(duration), 60)
            msg += f"\n⏱️ *Duration:* {mins}:{secs:02d}"
        await update.message.reply_text(msg, parse_mode='Markdown')

        await update.message.reply_text("⏳ Downloading... Please wait...")
        file_path, _ = download_media(url, is_audio)
        file_size = os.path.getsize(file_path)

        if file_size > TELEGRAM_MAX_FILE_SIZE:
            await update.message.reply_text("⚠️ File too large to send via Telegram (50 MB limit).")
        else:
            if is_audio:
                await update.message.reply_audio(audio=open(file_path, 'rb'))
            else:
                await update.message.reply_video(video=open(file_path, 'rb'))

        os.remove(file_path)
    except Exception as e:
        await update.message.reply_text(f"😥 Error: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot is running...")
    app.run_polling()
