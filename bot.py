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

# ==================== RATING VIEW ====================
class RatingView(ui.View):
    def __init__(self, video_message_id: int):
        super().__init__(timeout=300)  # 5 минут
        self.video_message_id = video_message_id

        # === ТВОИ ЭМОДЗИ (только эмодзи, без текста) ===
        emoji_ids = [
            1236025121919995924,
            1186400068765495326,
            1285518917384536147,
            1359852698941260016,
            1452281896984772700,
            1185699512698810419,
            1227332109400801320,
        ]

        for emoji_id in emoji_ids:
            emoji = bot.get_emoji(emoji_id)
            if emoji:
                button = ui.Button(style=discord.ButtonStyle.gray, emoji=emoji)
                button.callback = self.create_callback(emoji_id)
                self.add_item(button)

    def create_callback(self, emoji_id: int):
        async def callback(interaction: discord.Interaction):
            # Сохраняем оценку
            ratings[self.video_message_id][interaction.user.id] = emoji_id

            # Показываем обновлённый список оценок
            embed = await self.build_ratings_embed(interaction)
            await interaction.response.edit_message(embed=embed, view=None)

        return callback

    async def build_ratings_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📊 Рейтинг смехуятинки", color=0xFF0050)
        video_ratings = ratings.get(self.video_message_id, {})

        if not video_ratings:
            embed.description = "Пока никто не оценил это видео."
            return embed

        description = ""
        for user_id, emoji_id in video_ratings.items():
            user = interaction.guild.get_member(user_id) or await bot.fetch_user(user_id)
            emoji = bot.get_emoji(emoji_id)
            emoji_str = str(emoji) if emoji else "❔"

            description += f"{emoji_str} **{user.display_name}**\n"

        embed.description = description.strip()
        embed.set_footer(text="Нажми на кнопку Rate, чтобы изменить свою оценку")
        return embed


# ==================== ОСНОВНАЯ VIEW ПОД ВИДЕО ====================
class VideoView(ui.View):
    def __init__(self, info: dict, video_message_id: int):
        super().__init__(timeout=3600*6)  # 6 часов
        self.info = info
        self.video_message_id = video_message_id

    @ui.button(label="📄 Info", style=discord.ButtonStyle.blurple)
    async def show_info(self, interaction: discord.Interaction, button: ui.Button):
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
        """Открывает панель рейтинга"""
        view = RatingView(self.video_message_id)
        embed = await view.build_ratings_embed(interaction)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="🗑️ Delete", style=discord.ButtonStyle.red)
    async def delete_video(self, interaction: discord.Interaction, button: ui.Button):
        if (interaction.message.reference and interaction.user.id != interaction.message.reference.resolved.author.id) and \
           not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Только автор или модератор может удалить это видео.", ephemeral=True)
            return
        await interaction.message.delete()
        await interaction.response.send_message("✅ Видео удалено.", ephemeral=True)


# ==================== ОБРАБОТКА TIKTOK ====================
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

        view = VideoView(info, message.id) if settings["show_buttons"] else None

        await message.channel.send(
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
