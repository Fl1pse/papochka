import os
import discord
from discord.ext import commands
from discord import app_commands, ui
from yt_dlp import YoutubeDL
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

VIDEO_DIR = "videos"
os.makedirs(VIDEO_DIR, exist_ok=True)

# Глобальные настройки
settings = {
    "delete_original": False,
    "suppress_original": True,
    "show_buttons": True,
    "bot_enabled": True
}

# Хранилище оценок: {video_message_id: {user_id: emoji_id}}
ratings = defaultdict(dict)

# ==================== RATING VIEW (панель, которую видит только пользователь) ====================
class RatingView(ui.View):
    def __init__(self, video_message_id: int):
        super().__init__(timeout=300)  # 5 минут
        self.video_message_id = video_message_id

        # === Здесь вставляй ID своих серверных эмодзи ===
        # Замени числа на реальные ID эмодзи с твоего сервера
        emoji_ids = [
            1236025121919995924,   # 1 эмодзи (например "cry")
            1186400068765495326,   # 2
            1285518917384536147,   # 3
            1359852698941260016,   # 4
            1452281896984772700,   # 5
            1185699512698810419,   # 6
            1227332109400801320,   # 7 (например "rofl")
        ]

        labels = ["😭 Не смешно", "🙂 Слабовато", "👍 Норм", "😂 Смешно", "🤣 Очень смешно", "🔥 Огонь", "💀 Умер"]

        for i, (emoji_id, label) in enumerate(zip(emoji_ids, labels)):
            emoji = bot.get_emoji(emoji_id)
            button = ui.Button(label=label, style=discord.ButtonStyle.gray, emoji=emoji, row=i//4)
            button.callback = self.create_callback(emoji_id)
            self.add_item(button)

    def create_callback(self, emoji_id: int):
        async def callback(interaction: discord.Interaction):
            # Сохраняем оценку
            ratings[self.video_message_id][interaction.user.id] = emoji_id

            await interaction.response.edit_message(
                content="✅ Твоя оценка сохранена!",
                view=None
            )

            # Обновляем основное сообщение (опционально — можно показывать суммарный рейтинг)
            try:
                msg = await interaction.channel.fetch_message(self.video_message_id)
                await msg.edit(content=msg.content)  # триггер обновления
            except:
                pass

        return callback


# ==================== ОСНОВНАЯ VIEW ПОД ВИДЕО ====================
class VideoView(ui.View):
    def __init__(self, info: dict, video_message_id: int):
        super().__init__(timeout=3600*6)  # 6 часов
        self.info = info
        self.video_message_id = video_message_id

    @ui.button(label="📄 Info", style=discord.ButtonStyle.blurple)
    async def show_info(self, interaction: discord.Interaction, button: ui.Button):
        # ... (твой старый код Info остаётся без изменений)
        title = self.info.get('title', 'Без названия')
        uploader = self.info.get('uploader', 'Неизвестный автор')
        likes = self.info.get('like_count', 0)
        comments = self.info.get('comment_count', 0)
        shares = self.info.get('repost_count', self.info.get('share_count', 0))
        views = self.info.get('view_count', self.info.get('play_count', 0))

        embed = discord.Embed(title="📊 Информация о TikTok видео", color=0xFF0050)
        embed.add_field(name="📝 Название", value=title, inline=False)
        embed.add_field(name="👤 Автор", value=uploader, inline=False)
        embed.add_field(name="❤️ Лайки", value=f"{likes:,}", inline=True)
        embed.add_field(name="💬 Комментарии", value=f"{comments:,}", inline=True)
        embed.add_field(name="🔁 Репосты", value=f"{shares:,}", inline=True)
        embed.add_field(name="👁 Просмотры", value=f"{views:,}", inline=True)
        embed.set_footer(text=f"ID: {self.info.get('id', 'Неизвестно')}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="⭐ Rate", style=discord.ButtonStyle.green)
    async def rate_video(self, interaction: discord.Interaction, button: ui.Button):
        """Открывает панель с оценками — только для этого пользователя"""
        view = RatingView(self.video_message_id)
        await interaction.response.send_message(
            content="**Оцени видео:**\nВыбери насколько оно смешное:",
            view=view,
            ephemeral=True
        )

    @ui.button(label="🗑️ Delete", style=discord.ButtonStyle.red)
    async def delete_video(self, interaction: discord.Interaction, button: ui.Button):
        if (interaction.user.id != interaction.message.reference.resolved.author.id if interaction.message.reference else True) and \
           not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Только автор или модератор может удалить это видео.", ephemeral=True)
            return
        await interaction.message.delete()
        await interaction.response.send_message("✅ Видео удалено.", ephemeral=True)


# ==================== ОСТАЛЬНОЙ КОД (Settings, on_message и т.д.) ====================
# (оставляю без изменений, кроме добавления video_message_id)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not settings["bot_enabled"]:
        return

    tiktok_urls = [word for word in message.content.split()
                   if any(x in word for x in ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"])]

    if not tiktok_urls:
        return

    url = tiktok_urls[0]
    status_msg = await message.channel.send("🔄 Скачиваю видео из TikTok...")

    try:
        await message.add_reaction("⏳")

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

        await status_msg.edit(content="✅ **Готово!**")

        user_display_name = message.author.display_name
        video_content = f"**{user_display_name}** отправил TikTok"

        view = VideoView(info, message.id) if settings["show_buttons"] else None   # ← передаём message.id

        video_msg = await message.channel.send(
            content=video_content,
            file=discord.File(filename),
            view=view
        )

        if os.path.exists(filename):
            os.remove(filename)

        await message.remove_reaction("⏳", bot.user)
        await message.add_reaction("✅")

        if settings["suppress_original"]:
            try:
                await message.edit(suppress=True)
            except:
                pass

        if settings["delete_original"]:
            try:
                await message.delete()
            except:
                pass

    except Exception as e:
        await status_msg.edit(content=f"❌ Ошибка при скачивании: {str(e)[:300]}")
        await message.remove_reaction("⏳", bot.user)
        await message.add_reaction("❌")
        print(f"Ошибка с {url}: {e}")


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'✅ Бот запущен как {bot.user} | Работает во всех каналах')

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN не найден!")
    else:
        bot.run(token)
