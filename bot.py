import os
import discord
from discord.ext import commands
from discord import app_commands, ui
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import requests

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

VIDEO_DIR = "videos"
os.makedirs(VIDEO_DIR, exist_ok=True)

settings = {
    "delete_original": False,
    "suppress_original": True,
    "show_buttons": True,
    "bot_enabled": True
}

ratings = defaultdict(dict)


# ==================== RATING VIEW ====================
class RatingView(ui.View):
    def __init__(self, video_message_id: int):
        super().__init__(timeout=300)
        self.video_message_id = video_message_id

        emoji_ids = [
            1236025121919995924, 1186400068765495326, 1285518917384536147,
            1359852698941260016, 1452281896984772700, 1185699512698810419,
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
            ratings[self.video_message_id][interaction.user.id] = (emoji_id, datetime.now(timezone.utc))
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
        for user_id, (emoji_id, _) in video_ratings.items():
            user = interaction.guild.get_member(user_id) or await bot.fetch_user(user_id)
            emoji = bot.get_emoji(emoji_id)
            emoji_str = str(emoji) if emoji else "❔"
            description += f"{emoji_str} **{user.display_name}**\n"

        embed.description = description.strip()
        embed.set_footer(text="Нажми Rate, чтобы изменить оценку")
        return embed


# ==================== LEADERBOARD VIEW ====================
class LeaderboardView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.current_period = "all"

    async def get_leaderboard_data(self, period: str):
        now = datetime.now(timezone.utc)
        if period == "week":
            cutoff = now - timedelta(days=7)
        elif period == "month":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = datetime(2020, 1, 1, tzinfo=timezone.utc)

        user_stats = defaultdict(lambda: {"total": 0, "worst_emoji": None})

        for video_ratings in ratings.values():
            for user_id, (emoji_id, timestamp) in video_ratings.items():
                if timestamp < cutoff:
                    continue
                user_stats[user_id]["total"] += 1
                if emoji_id in [1236025121919995924, 1186400068765495326, 1285518917384536147]:
                    user_stats[user_id]["worst_emoji"] = emoji_id

        return sorted(user_stats.items(), key=lambda x: x[1]["total"], reverse=True)

    async def update_leaderboard(self, interaction: discord.Interaction):
        data = await self.get_leaderboard_data(self.current_period)
        embed = discord.Embed(title="🏆 Лидерборд смехуятинки", color=0xFFD700)

        for rank, (user_id, stats) in enumerate(data[:10], 1):
            user = interaction.guild.get_member(user_id) or await bot.fetch_user(user_id)
            if not user:
                continue
            emoji = bot.get_emoji(stats.get("worst_emoji")) if stats.get("worst_emoji") else None
            emoji_str = str(emoji) if emoji else "❔"
            name = f"#{rank} • {user.display_name}"
            value = f"{emoji_str} • Оценок: **{stats['total']}**"
            embed.add_field(name=name, value=value, inline=False)

        if not embed.fields:
            embed.description = "Пока нет оценок за выбранный период."

        try:
            await interaction.message.edit(embed=embed, view=self)
        except:
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="За неделю", style=discord.ButtonStyle.gray)
    async def week(self, interaction: discord.Interaction, button: ui.Button):
        self.current_period = "week"
        await self.update_leaderboard(interaction)

    @ui.button(label="За месяц", style=discord.ButtonStyle.gray)
    async def month(self, interaction: discord.Interaction, button: ui.Button):
        self.current_period = "month"
        await self.update_leaderboard(interaction)

    @ui.button(label="За всё время", style=discord.ButtonStyle.blurple)
    async def all_time(self, interaction: discord.Interaction, button: ui.Button):
        self.current_period = "all"
        await self.update_leaderboard(interaction)


# ==================== MEDIA VIEW ====================
class MediaView(ui.View):
    def __init__(self, info: dict, message_id: int):
        super().__init__(timeout=3600*6)
        self.info = info
        self.message_id = message_id

    @ui.button(label="📄 Info", style=discord.ButtonStyle.blurple)
    async def show_info(self, interaction: discord.Interaction, button: ui.Button):
        title = self.info.get('title', 'Без названия')
        uploader = self.info.get('uploader', 'Неизвестный автор')
        likes = self.info.get('like_count', 0)
        comments = self.info.get('comment_count', 0)
        shares = self.info.get('repost_count', self.info.get('share_count', 0))
        views = self.info.get('view_count', self.info.get('play_count', 0))

        embed = discord.Embed(title="📊 Информация о TikTok", color=0xFF0050)
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
        view = RatingView(self.message_id)
        embed = await view.build_ratings_embed(interaction)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="🗑️ Delete", style=discord.ButtonStyle.red)
    async def delete_video(self, interaction: discord.Interaction, button: ui.Button):
        if (interaction.message.reference and interaction.user.id != interaction.message.reference.resolved.author.id) and \
           not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Только автор или модератор может удалить это.", ephemeral=True)
            return
        await interaction.message.delete()
        await interaction.response.send_message("✅ Удалено.", ephemeral=True)


# ==================== ОБРАБОТКА TIKTOK ====================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not settings["bot_enabled"]:
        return

    tiktok_urls = [word for word in message.content.split()
                   if any(x in word for x in ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"])]

    if not tiktok_urls:
        return

    original_url = tiktok_urls[0]
    status_msg = await message.channel.send("🔄 Скачиваю из TikTok...")

    try:
        await message.add_reaction("⏳")

        # TikWM API
        api_url = f"https://api.tikwm.com/?url={original_url}&hd=1"
        response = requests.get(api_url, timeout=20)
        data = response.json()

        if data.get('code') != 0:
            raise Exception(data.get('msg', 'API error'))

        result = data['data']
        user_display_name = message.author.display_name
        content = f"**{user_display_name}** отправил TikTok"

        if result.get('images'):  # Фото-карусель
            files = []
            for i, img_url in enumerate(result['images'][:10]):
                img_data = requests.get(img_url, timeout=15).content
                files.append(discord.File(img_data, filename=f"photo_{i+1}.jpg"))

            if files:
                await message.channel.send(
                    content=content,
                    files=files,
                    view=MediaView(result, message.id) if settings["show_buttons"] else None
                )
            else:
                await message.channel.send(content=content + "\nНе удалось скачать фото.")
        else:  # Видео
            video_url = result.get('hdplay') or result.get('play')
            video_data = requests.get(video_url, timeout=20).content

            await message.channel.send(
                content=content,
                file=discord.File(video_data, filename="tiktok.mp4"),
                view=MediaView(result, message.id) if settings["show_buttons"] else None
            )

        await status_msg.edit(content="✅ **Готово!**")
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
        await status_msg.edit(content=f"❌ Не удалось скачать: {str(e)[:200]}")
        await message.remove_reaction("⏳", bot.user)
        await message.add_reaction("❌")
        print(f"Ошибка с {original_url}: {e}")


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'✅ Бот запущен как {bot.user} | TikWM API')


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN не найден!")
    else:
        bot.run(token)
