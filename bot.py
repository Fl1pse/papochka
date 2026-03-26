import os
import discord
from discord.ext import commands
from discord import app_commands, ui
from yt_dlp import YoutubeDL
from dotenv import load_dotenv

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

# ==================== VIDEO INFO VIEW ====================
class VideoView(ui.View):
    def __init__(self, info: dict, message_id: int):
        super().__init__(timeout=3600)  # 1 час
        self.info = info
        self.message_id = message_id

    @ui.button(label="Info", style=discord.ButtonStyle.blurple)
    async def show_info(self, interaction: discord.Interaction, button: ui.Button):
        likes = self.info.get('like_count', 0)
        comments = self.info.get('comment_count', 0)
        shares = self.info.get('repost_count', self.info.get('share_count', 0))
        views = self.info.get('view_count', self.info.get('play_count', 0))
        title = self.info.get('title', 'Без названия')

        embed = discord.Embed(title="📊 Информация о видео", color=0x00ff00)
        embed.add_field(name="Название", value=title[:256], inline=False)
        embed.add_field(name="❤️ Лайки", value=f"{likes:,}", inline=True)
        embed.add_field(name="💬 Комментарии", value=f"{comments:,}", inline=True)
        embed.add_field(name="🔁 Репосты", value=f"{shares:,}", inline=True)
        embed.add_field(name="👁 Просмотры", value=f"{views:,}", inline=True)
        embed.set_footer(text=f"ID видео: {self.info.get('id', 'Неизвестно')}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Delete", style=discord.ButtonStyle.red)
    async def delete_video(self, interaction: discord.Interaction, button: ui.Button):
        # Разрешаем удалять только автору сообщения или администраторам
        if interaction.user.id != interaction.message.reference.resolved.author.id and not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Ты не можешь удалить это видео.", ephemeral=True)
            return

        await interaction.message.delete()
        await interaction.response.send_message("✅ Видео удалено.", ephemeral=True)


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


# ==================== SLASH COMMAND ====================
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

        # Кнопки показываем только если включено в настройках
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
