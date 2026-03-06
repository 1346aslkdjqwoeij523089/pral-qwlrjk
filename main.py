import os
from flask import Flask, render_template
from threading import Thread
import nextcord
from nextcord.ext import commands
from nextcord.ext import tasks

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
intents.members = True  # Enable members intent for member events
intents.guilds = True

bot = commands.Bot(command_prefix="<", intents=intents)

# Channel IDs
MEMBER_COUNT_CHANNEL_ID = 1471478613038600328
WELCOME_CHANNEL_ID = 1464682633371062293
BOT_USER_ID = 1478894384597700669
DEVELOPER_USER_ID = 1261535675472281724

# Set bot activity and name
@bot.event
async def on_ready():
    await bot.change_presence(activity=nextcord.Activity(type=nextcord.ActivityType.playing, name="Los Angeles Roleplay"))
    print(f'Bot is logged in as {bot.user.name}')
    # Start the member count updater task
    update_member_count.start()

# Task to update member count every 10 minutes
@tasks.loop(minutes=10)
async def update_member_count():
    try:
        # Get the guild (assuming bot is in one server, or find by ID)
        for guild in bot.guilds:
            # Count members excluding bots
            member_count = len([member for member in guild.members if not member.bot])
            
            # Get the channel
            channel = bot.get_channel(MEMBER_COUNT_CHANNEL_ID)
            if channel:
                await channel.edit(name=f"Members: {member_count}")
                print(f"Updated member count to {member_count}")
    except Exception as e:
        print(f"Error updating member count: {e}")

# Event: When a new member joins the server
@bot.event
async def on_member_join(member):
    # Don't send welcome message for bots
    if member.bot:
        return
    
    try:
        # Get the welcome channel
        channel = bot.get_channel(WELCOME_CHANNEL_ID)
        if not channel:
            print(f"Welcome channel {WELCOME_CHANNEL_ID} not found")
            return
        
        # Create Image Embed 1 (link embed with welcome image)
        embed1 = nextcord.Embed()
        embed1.description = f"[Welcomelarp](https://cdn.discordapp.com/attachments/1479259996846948403/1479260063192584273/welcomelarp.png?ex=69ab63ca&is=69aa124a&hm=3c0da986deb94716651023791e37aa7998f5c98cd162ed8c5e4999993bcfc7a5&)"
        embed1.color = 0x004bae  # Sidebar color: 004bae
        embed1.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479260063192584273/welcomelarp.png?ex=69ab63ca&is=69aa124a&hm=3c0da986deb94716651023791e37aa7998f5c98cd162ed8c5e4999993bcfc7a5&")
        
        # Create Text Embed 2
        embed2 = nextcord.Embed(
            title="<:Offical_server:1475860128686411837> __Los Angeles Roleplay - New Member__",
            color=0x004bae  # Sidebar color: 004bae
        )
        embed2.description = f"Welcome to Los Angeles Roleplay, {member.mention}!\n\n" \
            "> To learn more about our community, check out <#1464682633371062296>.\n" \
            "> In need of assistance? Create a ticket in <#1464682633371062300>.\n" \
            "> Ensure you are properly verified within <#1464682633371062294>.\n"
        
        # Create Image Embed 3 (footer image)
        embed3 = nextcord.Embed()
        embed3.color = 0x004bae  # Sidebar color: 004bae
        embed3.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ab6798&is=69aa1618&hm=1d2252bf2f7eb6cfb39919584fada1db4f56e73a4721967df64e6dd509b38224&")
        
        # Send the embeds
        await channel.send(content=member.mention, embeds=[embed1, embed2, embed3])
        
    except Exception as e:
        print(f"Error sending welcome message: {e}")

# Event: When a message is sent
@bot.event
async def on_message(message):
    # Ignore messages from bots
    if message.author.bot:
        return
    
    # Check if the bot is mentioned in the message
    if BOT_USER_ID in [mention.id for mention in message.mentions]:
        try:
            # Get the bot's nickname in the guild
            bot_member = message.guild.get_member(BOT_USER_ID)
            bot_nickname = bot_member.nick if bot_member and bot_member.nick else bot_member.name if bot_member else "Los Angeles Roleplay"
            
            # Create Text Embed 1
            embed1 = nextcord.Embed(
                title=f"**{bot_nickname}**",
                color=0x004bae  # Sidebar color: 004bae
            )
            embed1.description = f"> Thanks for mention <@{BOT_USER_ID}>: Our Community Services bot.\n" \
                f"> `Prefix:` <\n" \
                f"> Developed by <@{DEVELOPER_USER_ID}>"
            
            # Create Image Embed 2 (footer image)
            embed2 = nextcord.Embed()
            embed2.color = 0x004bae  # Sidebar color: 004bae
            embed2.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ab6798&is=69aa1618&hm=1d2252bf2f7eb6cfb39919584fada1db4f56e73a4721967df64e6dd509b38224&")
            
            # Reply to the user
            await message.reply(embeds=[embed1, embed2])
            
        except Exception as e:
            print(f"Error responding to bot mention: {e}")
    
    # Process commands (if any)
    await bot.process_commands(message)

# Example command
@bot.command()
async def ping(ctx):
    await ctx.send('Pong! Los Angeles Roleplay is online!')

# Run the bot - use TOKEN environment variable (for Render.com deployment)
keep_alive()
bot.run(os.environ.get('TOKEN'))

