import os
import discord
from discord.ext import commands
from discord import app_commands, ui
from yt_dlp import YoutubeDL
from dotenv import load_dotenv
import re
import random

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

# Счётчик сообщений для рандомной реакции
message_counter = 0
MIN_MESSAGES = 2   # минимум сообщений между реакциями
MAX_MESSAGES = 9   # максимум сообщений между реакциями

# ==================== VIDEO INFO VIEW ====================
class VideoView(ui.View):
    def __init__(self, info: dict):
        super().__init__(timeout=3600)
        self.info = info

    @ui.button(label="📄 Info", style=discord.ButtonStyle.blurple)
    async def show_info(self, interaction: discord.Interaction, button: ui.Button):
        title = self.info.get('title', 'Без названия')
        display_name = self.info.get('uploader', 'Неизвестный автор')

        username = ""
        if self.info.get('uploader_url'):
            match = re.search(r'tiktok\.com/@([\w.]+)', self.info.get('uploader_url', ''))
            if match:
                username = match.group(1)
        if not username:
            username = self.info.get('uploader_id', '') or self.info.get('channel', '')

        if username and username != display_name:
            author_str = f"{display_name}\n@{username}"
        else:
            author_str = display_name

        likes = self.info.get('like_count', 0)
        comments = self.info.get('comment_count', 0)
        shares = self.info.get('repost_count', self.info.get('share_count', 0))
        views = self.info.get('view_count', self.info.get('play_count', 0))
        favorites = self.info.get('save_count', self.info.get('bookmark_count', self.info.get('favorites_count', 0)))

        clean_title = re.sub(r'#\w+', '', title).strip()
        if not clean_title:
            clean_title = title
        if len(clean_title) > 900:
            clean_title = clean_title[:897] + "..."

        tags = self.info.get('tags', self.info.get('hashtags', []))
        if not tags and title:
            tags = re.findall(r'#(\w+)', title)
        if isinstance(tags, list):
            tags_str = " ".join([f"#{tag}" for tag in tags]) if tags else "Нет тегов"
        else:
            tags_str = str(tags) if tags else "Нет тегов"
        if len(tags_str) > 900:
            tags_str = tags_str[:897] + "..."

        music_title = (self.info.get('track') or self.info.get('music_title') or self.info.get('music') or
                       self.info.get('original_sound_title') or "Original Sound")
        music_artist = (self.info.get('artist') or self.info.get('music_author') or
                        self.info.get('music_creator') or self.info.get('creator') or "")

        if "original sound" in music_title.lower():
            music_str = f"Original Sound — {display_name}"
        elif music_artist:
            music_str = f"{music_title} — {music_artist}"
        else:
            music_str = music_title

        upload_date = self.info.get('upload_date', '')
        formatted_date = f"{upload_date[6:8]}.{upload_date[4:6]}.{upload_date[0:4]}" if upload_date and len(upload_date) == 8 else "Неизвестно"

        embed = discord.Embed(title="📊 Информация о TikTok видео", color=0xFF0050)
    
        embed.add_field(name="📝 Название", value=clean_title, inline=False)
        embed.add_field(name="🏷️ Теги", value=tags_str, inline=False)
        embed.add_field(name="👤 Автор", value=author_str, inline=False)
        embed.add_field(name="🎵 Музыка", value=music_str, inline=False)
        embed.add_field(name="❤️ Лайки", value=f"{likes:,}", inline=True)
        embed.add_field(name="💬 Комментарии", value=f"{comments:,}", inline=True)
        embed.add_field(name="🔁 Репосты", value=f"{shares:,}", inline=True)
        embed.add_field(name="👁 Просмотры", value=f"{views:,}", inline=True)
        embed.add_field(name="⭐ Избранное", value=f"{favorites:,}", inline=True)
        embed.add_field(name="📅 Дата загрузки", value=formatted_date, inline=True)
    
        embed.set_footer(text=f"ID: {self.info.get('id', 'Неизвестно')} • Загружено через бот")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="🗑️ Delete", style=discord.ButtonStyle.red)
    async def delete_video(self, interaction: discord.Interaction, button: ui.Button):
        if (interaction.message.reference and
            interaction.user.id != interaction.message.reference.resolved.author.id) and \
           not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Только автор или модератор может удалить это видео.", ephemeral=True)
            return
        await interaction.message.delete()
        await interaction.response.send_message("✅ Сообщение с видео удалено.", ephemeral=True)


# ==================== SETTINGS VIEW ====================
class OptionsView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Delete Original", style=discord.ButtonStyle.red, row=0)
    async def toggle_delete(self, interaction: discord.Interaction, button: ui.Button):
        settings["delete_original"] = not settings["delete_original"]
        await self.update_settings(interaction)

    @ui.button(label="Suppress Original", style=discord.ButtonStyle.green, row=0)
    async def toggle_suppress(self, interaction: discord.Interaction, button: ui.Button):
        settings["suppress_original"] = not settings["suppress_original"]
        await self.update_settings(interaction)

    @ui.button(label="Show Buttons", style=discord.ButtonStyle.blurple, row=0)
    async def toggle_buttons(self, interaction: discord.Interaction, button: ui.Button):
        settings["show_buttons"] = not settings["show_buttons"]
        await self.update_settings(interaction)

    @ui.button(label="Turn Bot ON/OFF", style=discord.ButtonStyle.gray, row=1)
    async def toggle_bot(self, interaction: discord.Interaction, button: ui.Button):
        settings["bot_enabled"] = not settings["bot_enabled"]
        await self.update_settings(interaction)

    async def update_settings(self, interaction: discord.Interaction):
        status = "✅ **Включён**" if settings["bot_enabled"] else "⛔ **Выключен**"
        await interaction.response.edit_message(
            content=f"**Настройки бота**\n\n"
                    f"Delete Original: {'✅' if settings['delete_original'] else '❌'}\n"
                    f"Suppress Original: {'✅' if settings['suppress_original'] else '❌'}\n"
                    f"Show Buttons: {'✅' if settings['show_buttons'] else '❌'}\n\n"
                    f"Состояние бота: {status}",
            view=self
        )


@bot.tree.command(name="options", description="Открыть настройки бота")
async def options(interaction: discord.Interaction):
    status = "✅ **Включён**" if settings["bot_enabled"] else "⛔ **Выключен**"
    await interaction.response.send_message(
        content=f"**Настройки бота**\n\n"
                f"Delete Original: {'✅' if settings['delete_original'] else '❌'}\n"
                f"Suppress Original: {'✅' if settings['suppress_original'] else '❌'}\n"
                f"Show Buttons: {'✅' if settings['show_buttons'] else '❌'}\n\n"
                f"Состояние бота: {status}",
        view=OptionsView(),
        ephemeral=True
    )


# ==================== РАНДОМНАЯ РЕАКЦИЯ ЧЕРЕЗ СЛУЧАЙНОЕ КОЛИЧЕСТВО СООБЩЕНИЙ ====================
@bot.event
async def on_message(message: discord.Message):
    global message_counter

    message_counter += 1

    # TikTok-логика
    if not message.author.bot and settings["bot_enabled"]:
        tiktok_urls = [word for word in message.content.split()
                       if any(x in word for x in ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"])]
        if tiktok_urls:
            url = tiktok_urls[0]
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

                user_display_name = message.author.display_name
                video_content = f"**{user_display_name}** отправил TikTok"

                view = VideoView(info) if settings["show_buttons"] else None

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
                await message.remove_reaction("⏳", bot.user)
                await message.add_reaction("❌")
                print(f"Ошибка с {url}: {e}")

    # === Рандомная реакция через случайное количество сообщений ===
    if message.guild and message.guild.emojis:
        if message_counter >= random.randint(MIN_MESSAGES, MAX_MESSAGES):
            random_emoji = random.choice(message.guild.emojis)
            try:
                await message.add_reaction(random_emoji)
            except:
                pass
            message_counter = 0  # сбрасываем счётчик после реакции


@bot.event
async def on_ready():
    global message_counter
    message_counter = 0
    await bot.tree.sync()
    print(f'✅ Бот запущен как {bot.user} | Реагирует через случайное количество сообщений')


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN не найден!")
    else:
        bot.run(token)
