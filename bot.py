import os
import discord
from discord.ext import commands
from discord import app_commands
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

# ==================== SETTINGS VIEW ====================
class OptionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Delete Original", style=discord.ButtonStyle.red, row=0)
    async def toggle_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings["delete_original"] = not settings["delete_original"]
        await self.update_settings(interaction)

    @discord.ui.button(label="Suppress Original", style=discord.ButtonStyle.green, row=0)
    async def toggle_suppress(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings["suppress_original"] = not settings["suppress_original"]
        await self.update_settings(interaction)

    @discord.ui.button(label="Show Buttons", style=discord.ButtonStyle.blurple, row=0)
    async def toggle_buttons(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings["show_buttons"] = not settings["show_buttons"]
        await self.update_settings(interaction)

    @discord.ui.button(label="Turn Bot ON/OFF", style=discord.ButtonStyle.gray, row=1)
    async def toggle_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
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

    # Сообщение о скачивании
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

        # Меняем статус на "Готово!"
        await status_msg.edit(content=f"✅ **Готово!**")

        # Отправляем видео с именем пользователя
        user_display_name = message.author.display_name
        video_content = f"**{user_display_name}** отправил TikTok"

        video_msg = await message.channel.send(
            content=video_content,
            file=discord.File(filename)
        )

        if os.path.exists(filename):
            os.remove(filename)

        await message.remove_reaction("⏳", bot.user)
        await message.add_reaction("✅")

        # === Suppress Original ===
        if settings["suppress_original"]:
            try:
                await message.edit(suppress=True)   # убирает embed от TikTok
            except:
                pass

        # === Delete Original ===
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

# ==================== ЗАПУСК ====================
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
