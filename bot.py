import os
import discord
from discord.ext import commands
from yt_dlp import YoutubeDL
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

VIDEO_DIR = "videos"
os.makedirs(VIDEO_DIR, exist_ok=True)

@bot.event
async def on_ready():
    print(f'✅ Бот запущен как {bot.user} | Работает во ВСЕХ каналах')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Проверяем, есть ли в сообщении ссылка на TikTok
    tiktok_urls = [word for word in message.content.split() 
                   if any(x in word for x in ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"])]

    if not tiktok_urls:
        return

    url = tiktok_urls[0]
    await message.add_reaction("⏳")

    try:
        await message.channel.send("🔄 Скачиваю видео из TikTok...")

        ydl_opts = {
            'format': 'best',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(VIDEO_DIR, '%(id)s_%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        await message.channel.send(file=discord.File(filename))

        if os.path.exists(filename):
            os.remove(filename)

        await message.remove_reaction("⏳", bot.user)
        await message.add_reaction("✅")

    except Exception as e:
        await message.remove_reaction("⏳", bot.user)
        await message.add_reaction("❌")
        await message.channel.send(f"❌ Ошибка при скачивании: {str(e)[:300]}")
        print(f"Ошибка с {url}: {e}")

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN не найден в .env!")
    else:
        bot.run(token)