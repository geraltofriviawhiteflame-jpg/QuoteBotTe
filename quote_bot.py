import os
import logging
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from openai import OpenAI
from fastapi import FastAPI, Request
import uvicorn
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openrouter/free')
WEBHOOK_URL = os.getenv('WEBHOOK_URL') # e.g. https://your-domain.com/webhook

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Initialize OpenRouter Client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Initialize Telegram Application
application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI to handle Telegram bot setup."""
    # Set webhook on startup
    if WEBHOOK_URL:
        webhook_path = f"{WEBHOOK_URL}/webhook"
        await application.bot.set_webhook(url=webhook_path)
        logging.info(f"Webhook set to {webhook_path}")
    
    async with application:
        await application.start()
        yield
        await application.stop()

app = FastAPI(lifespan=lifespan)

async def get_quote_from_llm(topic: str = "success and positivity"):
    """Fetch a high-impact motivational session from OpenRouter LLM."""
    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a world-class performance coach. Deliver high-impact motivation. "
                        "Use ONLY HTML tags for formatting (<b>, <i>, <u>). DO NOT use Markdown symbols like ** or __.\n\n"
                        "Each response MUST follow this exact HTML structure:\n\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "🌟 <b>DAILY PERSPECTIVE</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "<i>“Quote text”</i>\n"
                        "— <b>Author Name</b>\n\n"
                        "💡 <b>THE INSIGHT</b>\n"
                        "[Concise analysis focused on mindset shift]\n\n"
                        "🔥 <b>THE ACTION PLAN</b>\n"
                        "Your mission today is [Specific Task]...\n\n"
                        "🚀 <b>GO GET IT!</b>"
                    )
                },
                {"role": "user", "content": f"Deliver a high-impact motivational session on the topic: {topic}."}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error fetching quote: {e}")
        return "Oops! I couldn't find a quote right now, but stay positive! 🌟"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /start."""
    await update.message.reply_text(
        "Hello! I am your Motivational Performance Coach. 🌟\n\n"
        "Send me a topic to get your daily mission!",
        parse_mode='HTML'
    )

async def send_quote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages and provide quotes."""
    user_text = update.message.text
    await update.message.reply_chat_action(action="typing")
    
    quote = await get_quote_from_llm(user_text)
    await update.message.reply_text(quote, parse_mode='HTML')

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), send_quote_handler))

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Endpoint for Telegram to send updates via Webhook."""
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"status": "ok"}

@app.get("/")
async def index():
    return {"message": "Motivational Quote Bot is running!"}

if __name__ == '__main__':
    if not TELEGRAM_BOT_TOKEN or not OPENROUTER_API_KEY:
        print("Error: TELEGRAM_BOT_TOKEN and OPENROUTER_API_KEY must be set in .env file.")
    else:
        # For local testing, you can use polling or uvicorn
        # If WEBHOOK_URL is set, use uvicorn, otherwise use polling for convenience
        if WEBHOOK_URL:
            uvicorn.run(app, host="0.0.0.0", port=8000)
        else:
            print("No WEBHOOK_URL found. Falling back to polling...")
            application.run_polling()
