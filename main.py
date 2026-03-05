import os
from flask import Flask, render_template
from threading import Thread
import nextcord
from nextcord.ext import commands

# Flask app for keeping the bot alive
app = Flask('')

@app.route('/')
def home():
    return "Los Angeles Roleplay Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# Bot setup
intents = nextcord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Set bot activity and name
@bot.event
async def on_ready():
    await bot.change_presence(activity=nextcord.Activity(type=nextcord.ActivityType.playing, name="Los Angeles Roleplay"))
    print(f'Bot is logged in as {bot.user.name}')

# Example command
@bot.command()
async def ping(ctx):
    await ctx.send('Pong! Los Angeles Roleplay is online!')

# Run the bot - use TOKEN environment variable (for Render.com deployment)
keep_alive()
bot.run(os.environ.get('TOKEN'))

