import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

TOKEN = "7955482156:AAEyB3s_GkVxLjg8rHZNVJ6_neX8K9hsTnQ"

# Store user selection temporarily
user_selections = {}

# 🔍 Multi-anime search with pagination
def search_anime(query: str, page: int = 1):
    url = "https://graphql.anilist.co"
    query_str = '''
    query ($search: String, $page: Int) {
      Page(perPage: 10, page: $page) {
        pageInfo {
          total
          currentPage
          lastPage
          hasNextPage
        }
        media(search: $search, type: ANIME) {
          id
          format
          title {
            romaji
            english
          }
        }
      }
    }
    '''
    variables = {"search": query, "page": page}
    response = requests.post(url, json={"query": query_str, "variables": variables})
    if response.status_code != 200:
        return [], None
    data = response.json()["data"]["Page"]
    return data["media"], data["pageInfo"]

# 🔍 Multi-manga search with pagination
def search_manga(query: str, page: int = 1):
    url = "https://graphql.anilist.co"
    query_str = '''
    query ($search: String, $page: Int) {
      Page(perPage: 10, page: $page) {
        pageInfo {
          total
          currentPage
          lastPage
          hasNextPage
        }
        media(search: $search, type: MANGA) {
          id
          format
          title {
            romaji
            english
          }
          isAdult
        }
      }
    }
    '''
    variables = {"search": query, "page": page}
    response = requests.post(url, json={"query": query_str, "variables": variables})
    if response.status_code != 200:
        return [], None
    data = response.json()["data"]["Page"]
    return data["media"], data["pageInfo"]

# 🎯 Get anime details
def get_anime_by_id(anime_id: int):
    url = "https://graphql.anilist.co"
    query_str = '''
    query ($id: Int) {
      Media(id: $id, type: ANIME) {
        id
        format
        title {
          romaji
          english
        }
        episodes
        status
        startDate {
          year
        }
        studios(isMain: true) {
          nodes {
            name
          }
        }
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

# 📚 Get manga details
def get_manga_by_id(manga_id: int):
    url = "https://graphql.anilist.co"
    query_str = '''
    query ($id: Int) {
      Media(id: $id, type: MANGA) {
        id
        format
        title {
          romaji
          english
        }
        chapters
        status
        startDate {
          year
        }
        staff(role: "Story & Art") {
          nodes {
            name {
              full
            }
          }
        }
        genres
        description
        siteUrl
        isAdult
      }
    }
    '''
    response = requests.post(url, json={"query": query_str, "variables": {"id": manga_id}})
    if response.status_code != 200:
        return None
    return response.json()["data"]["Media"]

# 🚀 /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send an anime or manga title and I'll fetch all related formats from AniList!")

# 📩 User sends title - ask for type
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    title_query = update.message.text.strip()
    
    # Store the query in context for later use
    context.user_data['last_query'] = title_query
    
    # Ask user if they want anime or manga
    keyboard = [
        [InlineKeyboardButton("🎬 Anime", callback_data=f"type_anime_{title_query}")],
        [InlineKeyboardButton("📚 Manga/Manhwa/Novel", callback_data=f"type_manga_{title_query}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔍 What type are you looking for?", reply_markup=reply_markup)

# 🔘 User selects anime/manga type or specific title
async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    
    if data.startswith('type_'):
        # User selected anime or manga type
        parts = data.split('_', 2)
        if len(parts) == 3:
            media_type, search_query = parts[1], parts[2]
            await show_search_results(query, media_type, search_query, 1)
    
    elif data.startswith('page_'):
        # User wants to change page
        parts = data.split('_')
        if len(parts) == 4:
            media_type, search_query, page_str = parts[1], parts[2], parts[3]
            await show_search_results(query, media_type, search_query, int(page_str))
    
    else:
        # User selected a specific title
        parts = data.split('_')
        if len(parts) == 2:
            media_type, item_id = parts[0], int(parts[1])
            
            if media_type == "anime":
                await handle_anime_selection(query, item_id)
            else:  # manga
                await handle_manga_selection(query, item_id)

# 🔍 Show search results with pagination
async def show_search_results(query, media_type: str, search_query: str, page: int = 1):
    if media_type == "anime":
        results, page_info = search_anime(search_query, page)
        media_text = "anime"
    else:  # manga
        results, page_info = search_manga(search_query, page)
        media_text = "manga"
    
    if not results:
        await query.edit_message_text(f"❌ Couldn't find any {media_text} with that name.")
        return

    keyboard = []
    
    # Add results
    for item in results:
        name = item["title"]["english"] or item["title"]["romaji"]
        # Truncate long names
        if len(name) > 50:
            name = name[:47] + "..."
        label = f"{name} ({item['format']})"
        callback_data = f"{media_type}_{item['id']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    
    # Add pagination buttons
    pagination_buttons = []
    
    # Previous page button
    if page > 1:
        pagination_buttons.append(
            InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{media_type}_{search_query}_{page-1}")
        )
    
    # Page info
    if page_info and page_info['lastPage'] > 1:
        pagination_buttons.append(
            InlineKeyboardButton(f"Page {page}/{page_info['lastPage']}", callback_data="ignore")
        )
    
    # Next page button
    if page_info and page_info['hasNextPage']:
        pagination_buttons.append(
            InlineKeyboardButton("Next ➡️", callback_data=f"page_{media_type}_{search_query}_{page+1}")
        )
    
    if pagination_buttons:
        keyboard.append(pagination_buttons)
    
    # Add back to search type button
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Type Selection", callback_data=f"type_back_{search_query}")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = f"🎞 Found {len(results)} {media_text} results for '{search_query}' (Page {page})"
    if page_info and page_info['total']:
        message_text = f"🎞 Found {page_info['total']} {media_text} results for '{search_query}' (Page {page})"
    
    await query.edit_message_text(message_text, reply_markup=reply_markup)

# 🔙 Handle back to type selection
async def handle_back_to_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    search_query = query.data.split('_', 2)[2]
    
    keyboard = [
        [InlineKeyboardButton("🎬 Anime", callback_data=f"type_anime_{search_query}")],
        [InlineKeyboardButton("📚 Manga/Manhwa/Novel", callback_data=f"type_manga_{search_query}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"🔍 What type are you looking for '{search_query}'?", reply_markup=reply_markup)

# 🎬 Handle anime selection
async def handle_anime_selection(query, anime_id: int):
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
    # Using your original cover image format
    cover_image = f"https://img.anili.st/media/{anime['id']}"
    site_url = anime["siteUrl"]
    year = anime.get("startDate", {}).get("year", "N/A")

    formatted = (
        f"{title} | {anime_type} | {episodes} | {studio} | {status} | "
        f"{genres} | {synopsis} | {cover_image} | {site_url} | {year}"
    )

    await query.edit_message_text(formatted)

# 📚 Handle manga selection
async def handle_manga_selection(query, manga_id: int):
    manga = get_manga_by_id(manga_id)

    if not manga:
        await query.edit_message_text("❌ Couldn't load manga details.")
        return

    # Map format to the required type options
    format_map = {
        "MANGA": "MANGA",
        "NOVEL": "NOVEL", 
        "ONE_SHOT": "ONE_SHOT",
        "MANHWA": "MANHWA",
        "MANHUA": "MANHUA"
    }
    
    title = manga["title"]["english"] or manga["title"]["romaji"]
    manga_type = format_map.get(manga.get("format", ""), manga.get("format", "N/A").upper())
    chapters = manga.get("chapters", "N/A")
    
    # Fix for author - handle empty staff nodes
    author = "N/A"
    if manga.get("staff") and manga["staff"].get("nodes"):
        author = manga["staff"]["nodes"][0]["name"]["full"]
    
    status = manga.get("status", "N/A").upper()
    genres = ",".join(manga["genres"]) if manga["genres"] else "N/A"
    synopsis = manga.get("description", "").replace("<br>", "").replace("\n", " ").strip()
    if len(synopsis) > 150:
        synopsis = synopsis[:150].rsplit(" ", 1)[0] + "..."
    # Using same cover image format as anime
    cover_image = f"https://img.anili.st/media/{manga['id']}"
    site_url = manga["siteUrl"]
    year = manga.get("startDate", {}).get("year", "N/A")
    adult = str(manga.get("isAdult", False)).lower()

    formatted = (
        f"{title} | {manga_type} | {chapters} | {author} | {status} | "
        f"{genres} | {synopsis} | {cover_image} | {site_url} | {year} | {adult}"
    )

    await query.edit_message_text(formatted)

# 🧠 Main runner
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_selection, pattern="^(type_|page_|anime_|manga_)"))
    
    # Handle back button separately
    app.add_handler(CallbackQueryHandler(handle_back_to_type, pattern="^type_back_"))
    
    app.run_polling()
