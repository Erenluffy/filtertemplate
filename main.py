import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from flask import Flask, request

# ✅ Use env var instead of hardcoding
TOKEN = os.getenv("BOT_TOKEN", "AAHc75il2BECWK39tiPv4pVf-gZdPt4MFcw")
APP_URL = os.getenv("APP_URL", "https://tart-berna-ravibots-bf0b1400.koyeb.app/")

app = Flask(__name__)
telegram_app = ApplicationBuilder().token(TOKEN).build()

# 🔍 Multi-anime search
def search_anime(query: str):
    url = "https://graphql.anilist.co"
    query_str = '''
    query ($search: String) {
      Page(perPage: 10) {
        media(search: $search, type: ANIME) {
          id
          format
          title { romaji english }
        }
      }
    }
    '''
    response = requests.post(url, json={"query": query_str, "variables": {"search": query}})
    if response.status_code != 200:
        return []
    return response.json()["data"]["Page"]["media"]

# 🎯 Get anime details
def get_anime_by_id(anime_id: int):
    url = "https://graphql.anilist.co"
    query_str = '''
    query ($id: Int) {
      Media(id: $id, type: ANIME) {
        id
        format
        title { romaji english }
        episodes
        status
        startDate { year }
        studios(isMain: true) { nodes { name } }
        genres
        description
        siteUrl
      }
    }
    '''
    response = requests.post(url, json={"query": query_str, "variables": {"id": anime_id}})
    if response.status_code != 200:
        return None
    return response.json()["data"]["Media"]

# 🚀 /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send an anime title and I'll fetch all related formats from AniList!")

# 📩 User sends anime title
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    title_query = update.message.text.strip()
    results = search_anime(title_query)
    if not results:
        await update.message.reply_text("❌ Couldn't find any anime with that name.")
        return

    keyboard = [
        [InlineKeyboardButton((anime["title"]["english"] or anime["title"]["romaji"]) + f" ({anime['format']})", 
                              callback_data=str(anime["id"]))]
        for anime in results
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎞 Select the correct anime format:", reply_markup=reply_markup)

# 🔘 User taps on a button
async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_id = int(query.data)
    anime = get_anime_by_id(anime_id)
    if not anime:
        await query.edit_message_text("❌ Couldn't load anime details.")
        return

    title = anime["title"]["english"] or anime["title"]["romaji"]
    anime_type = anime.get("format", "N/A").upper()
    episodes = anime.get("episodes", "N/A")
    studio = anime["studios"]["nodes"][0]["name"] if anime["studios"]["nodes"] else "N/A"
    status = anime.get("status", "N/A").capitalize()
    genres = ",".join(anime["genres"]) if anime["genres"] else "N/A"
    synopsis = anime.get("description", "").replace("<br>", "").replace("\n", " ").strip()
    if len(synopsis) > 150:
        synopsis = synopsis[:150].rsplit(" ", 1)[0] + "..."
    cover_image = f"https://img.anili.st/media/{anime['id']}"
    site_url = anime["siteUrl"]
    year = anime.get("startDate", {}).get("year", "N/A")

    formatted = (
        f"{title} | {anime_type} | {episodes} | {studio} | {status} | "
        f"{genres} | {synopsis} | {cover_image} | {site_url} | {year}"
    )
    await query.edit_message_text(formatted)

# ✅ Register handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_handler(CallbackQueryHandler(handle_selection))

# 🌍 Flask route for webhook
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok", 200

# 📌 Setup webhook automatically
@app.route("/")
def index():
    telegram_app.bot.set_webhook(f"{APP_URL}/{TOKEN}")
    return "Webhook set!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
