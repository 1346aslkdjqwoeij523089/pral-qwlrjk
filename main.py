"""
Los Angeles Roleplay (LARP) Services Bot
Discord Bot for LARP Server Management
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('LARPServices')

# ============== CONFIGURATION ==============
GUILD_ID = 1464682632204779602
BOT_PREFIX = "<"
SIDEBAR_COLOR = 0x004bae

# Channel IDs
WELCOME_CHANNEL = 1464682633371062293
MEMBERCOUNT_VC = 1471478613038600328
SESSION_CHANNEL = 1464682633559801939
SESSION_STATUS_CHANNEL = 1480013219199451308
SESSION_LOG_CHANNEL = 1480024519677706382
STAFF_CHAT = 1464682633853407327
SESSION_PING_ROLE = 1465771610312278180
SESSION_START_MESSAGE = 1480023088799416451

# Role IDs
ROLE_FOUNDATION = 1464682632754233539
ROLE_EXECUTIVE = 1466490625259212821
ROLE_MANAGEMENT = 1464682632754233535
ROLE_HIGH_RANKING = 1464682632729071818
ROLE_INTERNAL_AFFAIRS = 1464682632661958858
ROLE_ADMINISTRATION = 1464682632661958852
ROLE_MODERATION = 1464682632645185848
ROLE_STAFF = 1464682632645185843
ROLE_BOT_DEV = 1479003906531917886

# Session Settings
SESSION_SHUTDOWN_COOLDOWN = 15  # minutes
SESSION_CHECK_INTERVAL = 60  # minutes

# ============== DATA FILES ==============
DATA_DIR = "bot_data"
os.makedirs(DATA_DIR, exist_ok=True)

AFK_FILE = os.path.join(DATA_DIR, "afk.json")
SESSION_FILE = os.path.join(DATA_DIR, "session.json")
DM_LOG_FILE = os.path.join(DATA_DIR, "dm_log.txt")
SESSION_LOG_FILE = os.path.join(DATA_DIR, "session_log.txt")
AFK_LOG_FILE = os.path.join(DATA_DIR, "afk_log.txt")

# ============== HELPER FUNCTIONS ==============
def load_json(filepath: str, default: dict = None) -> dict:
    if default is None:
        default = {}
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def save_json(filepath: str, data: dict):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

def append_log(filepath: str, message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filepath, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

def get_color() -> discord.Color:
    return discord.Color(SIDEBAR_COLOR)

def has_role(member: discord.Member, role_id: int) -> bool:
    return any(role.id == role_id for role in member.roles)

def has_any_role(member: discord.Member, role_ids: List[int]) -> bool:
    return any(has_role(member, rid) for rid in role_ids)

def is_executive_plus(member: discord.Member) -> bool:
    return has_any_role(member, [ROLE_EXECUTIVE, ROLE_BOT_DEV])

def is_management_plus(member: discord.Member) -> bool:
    return has_any_role(member, [ROLE_MANAGEMENT, ROLE_EXECUTIVE, ROLE_BOT_DEV])

def is_foundation_plus(member: discord.Member) -> bool:
    return has_any_role(member, [ROLE_FOUNDATION, ROLE_MANAGEMENT, ROLE_EXECUTIVE, ROLE_BOT_DEV])

def is_staff(member: discord.Member) -> bool:
    return has_any_role(member, [ROLE_STAFF, ROLE_MODERATION, ROLE_ADMINISTRATION, ROLE_INTERNAL_AFFAIRS, 
                                  ROLE_HIGH_RANKING, ROLE_MANAGEMENT, ROLE_EXECUTIVE, ROLE_FOUNDATION, ROLE_BOT_DEV])

# ============== BOT SETUP ==============
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

# ============== GLOBAL VARIABLES ==============
session_vote_message = None
session_vote_channel = None
session_active = False
session_start_time = None
session_starter_id = None
vote_threshold = None
vote_message_id = None
session_check_task = None

# ============== COGS ==============
class SessionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
class AFKCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

# ============== EVENTS ==============
@bot.event
async def on_ready():
    global guild
    guild = bot.get_guild(GUILD_ID)
    
    # Sync slash commands
    await bot.tree.sync()
    logger.info(f"Bot is ready as {bot.user}")
    
    # Start background tasks
    update_membercount.start()
    check_session_status.start()
    
    # Load session data
    load_session_data()
    
    # Send startup message to session log channel
    session_log = bot.get_channel(SESSION_LOG_CHANNEL)
    if session_log:
        await session_log.send(embed=discord.Embed(
            title="Bot Started",
            description=f"LARP Services Bot has been restarted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            color=get_color()
        ))

@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID:
        return
    
    welcome_channel = bot.get_channel(WELCOME_CHANNEL)
    if not welcome_channel:
        return
    
    # Create welcome embed
    embed = discord.Embed(color=get_color())
    embed.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479260063192584273/welcomelarp.png?ex=69ae06ca&is=69acb54a&hm=e3cf31d81d9dee35659908000b6d6ad4c2cc9831e57c719cac8c7a6e8d7bfc85&")
    
    await welcome_channel.send(content=member.mention, embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Check for AFK system
    afk_data = load_json(AFK_FILE)
    user_id = str(message.author.id)
    
    if user_id in afk_data:
        # User is back from AFK
        afk_info = afk_data[user_id]
        mentions = afk_info.get('mentions', [])
        
        # Remove AFK status
        nickname = message.author.display_name
        if nickname.startswith("AFK • "):
            try:
                await message.author.edit(nick=nickname[7:])
            except:
                pass
        
        # Show who mentioned them
        if mentions:
            mention_text = ", ".join([f"**{m['name']}**" for m in mentions])
            embed = discord.Embed(
                title=f"Welcome back, {message.author.display_name}!",
                description=f"You were mentioned by {mention_text} while you were AFK.",
                color=get_color()
            )
            await message.author.send(embed=embed)
        
        # Clear AFK data
        del afk_data[user_id]
        save_json(AFK_FILE, afk_data)
        
        embed = discord.Embed(
            title="AFK Removed",
            description=f"Welcome back! Your AFK status has been removed.",
            color=get_color()
        )
        await message.channel.send(embed=embed, delete_after=5)
    
    # Process commands
    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    # Track deleted messages for session channel cleanup
    pass

# ============== BACKGROUND TASKS ==============
@tasks.loop(minutes=15)
async def update_membercount():
    global guild
    if not guild:
        guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    
    vc = bot.get_channel(MEMBERCOUNT_VC)
    if not vc:
        return
    
    # Count members excluding bots
    member_count = len([m for m in guild.members if not m.bot])
    
    try:
        await vc.edit(name=f"Members: {member_count}")
        logger.info(f"Updated membercount to {member_count}")
    except Exception as e:
        logger.error(f"Failed to update membercount: {e}")

@tasks.loop(minutes=1)
async def check_session_status():
    """Check session status and handle auto-DM/auto-shutdown"""
    global session_active, session_start_time, session_starter_id, session_check_task
    
    session_data = load_json(SESSION_FILE)
    
    if not session_data.get('active', False):
        return
    
    if not session_start_time or not session_starter_id:
        return
    
    elapsed = datetime.now() - session_start_time
    elapsed_minutes = elapsed.total_seconds() / 60
    
    # After 1 hour - DM the starter
    if elapsed_minutes >= 60 and elapsed_minutes < 120:
        if not session_data.get('hourly_dm_sent', False):
            await send_session_status_dm(session_starter_id, 1)
            session_data['hourly_dm_sent'] = True
            save_json(SESSION_FILE, session_data)
    
    # After 2 hours - DM management and auto-shutdown if no response
    if elapsed_minutes >= 120:
        if not session_data.get('final_dm_sent', False):
            await send_session_status_dm_management()
            session_data['final_dm_sent'] = True
            save_json(SESSION_FILE, session_data)
            # Auto shutdown after 2 hours
            await shutdown_session_auto()

async def send_session_status_dm(user_id: int, hour: int):
    """Send DM to session starter asking about session status"""
    global guild
    if not guild:
        guild = bot.get_guild(GUILD_ID)
    
    user = guild.get_member(user_id)
    if not user:
        return
    
    embed = discord.Embed(color=get_color())
    embed.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
    
    embed2 = discord.Embed(
        title="<:Offical_server:1475860128686411837> | Session Management",
        description=f"As the session was started by you approximately an hour ago, please answer this question:\n> Is it currently still active?",
        color=get_color()
    )
    embed2.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
    
    view = SessionStatusView()
    await user.send(embeds=[embed, embed2, embed2], view=view)

async def send_session_status_dm_management():
    """Send DM to management role about session status"""
    global guild
    if not guild:
        guild = bot.get_guild(GUILD_ID)
    
    management_role = guild.get_role(ROLE_MANAGEMENT)
    executive_role = guild.get_role(ROLE_EXECUTIVE)
    
    if not management_role:
        return
    
    embed = discord.Embed(color=get_color())
    embed.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
    
    embed2 = discord.Embed(
        title="<:Offical_server:1475860128686411837> | Session Management",
        description=f"The session starter has not responded for 1 hour. Please answer:\n> Is the session currently still active?",
        color=get_color()
    )
    embed2.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
    
    for member in guild.members:
        if management_role in member.roles or (executive_role and executive_role in member.roles):
            try:
                view = SessionStatusView()
                await member.send(embeds=[embed, embed2, embed2], view=view)
            except:
                pass

async def shutdown_session_auto():
    """Auto shutdown session after 2 hours of inactivity"""
    global session_active, session_start_time, session_starter_id
    
    session_active = False
    session_start_time = None
    session_starter_id = None
    
    # Update session status channel
    status_channel = bot.get_channel(SESSION_STATUS_CHANNEL)
    if status_channel:
        await status_channel.edit(name="Sessions: 🔴")
    
    # Save session data
    session_data = load_json(SESSION_FILE)
    session_data['active'] = False
    session_data['start_time'] = None
    session_data['starter_id'] = None
    session_data['hourly_dm_sent'] = False
    session_data['final_dm_sent'] = False
    save_json(SESSION_FILE, session_data)
    
    # Send shutdown embed
    session_channel = bot.get_channel(SESSION_CHANNEL)
    if session_channel:
        embed = discord.Embed(
            description=f"A session has been shut down automatically due to inactivity. Thank you for joining today's session. See you soon!",
            color=get_color()
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
        
        await session_channel.send(embed=embed)

# ============== VIEW CLASSES ==============
class SessionStatusView(discord.ui.View):
    def __init__(self):
        super().__init__()
        
        dropdown = discord.ui.Select(
            placeholder="Select an option",
            options=[
                discord.SelectOption(label="Yes", value="yes"),
                discord.SelectOption(label="No", value="no")
            ]
        )
        dropdown.callback = self.status_selected
        self.add_item(dropdown)
    
    async def status_selected(self, interaction: discord.Interaction):
        value = interaction.data['values'][0]
        
        if value == "no":
            # Shutdown session
            await shutdown_session_by_user(interaction.user)
            await interaction.response.send_message("Session has been shut down.", ephemeral=True)
        else:
            await interaction.response.send_message("Session remains active.", ephemeral=True)

class SessionManagementView(discord.ui.View):
    def __init__(self, session_active: bool):
        super().__init__()
        
        if session_active:
            self.add_item(discord.ui.Button(label="Boost Session", style=discord.ButtonStyle.success, custom_id="session_boost"))
            self.add_item(discord.ui.Button(label="Shutdown Session", style=discord.ButtonStyle.danger, custom_id="session_shutdown"))
            self.add_item(discord.ui.Button(label="Session Full", style=discord.ButtonStyle.primary, custom_id="session_full"))
        else:
            self.add_item(discord.ui.Button(label="Initiate Session Vote", style=discord.ButtonStyle.primary, custom_id="session_vote"))
            self.add_item(discord.ui.Button(label="Start Session", style=discord.ButtonStyle.success, custom_id="session_start"))

# ============== HELPER FUNCTIONS ==============
def load_session_data():
    global session_active, session_start_time, session_starter_id
    session_data = load_json(SESSION_FILE)
    session_active = session_data.get('active', False)
    if session_data.get('start_time'):
        session_start_time = datetime.fromisoformat(session_data['start_time'])
    session_starter_id = session_data.get('starter_id')

async def save_session_data(active: bool, starter_id: int = None):
    global session_active, session_start_time, session_starter_id
    session_data = load_json(SESSION_FILE)
    session_data['active'] = active
    if active:
        session_start_time = datetime.now()
        session_starter_id = starter_id
        session_data['start_time'] = session_start_time.isoformat()
        session_data['starter_id'] = starter_id
        session_data['hourly_dm_sent'] = False
        session_data['final_dm_sent'] = False
    else:
        session_start_time = None
        session_starter_id = None
        session_data['start_time'] = None
        session_data['starter_id'] = None
    save_json(SESSION_FILE, session_data)

async def cleanup_session_channel():
    """Delete messages in session channel except the pinned start message"""
    session_channel = bot.get_channel(SESSION_CHANNEL)
    if not session_channel:
        return
    
    pinned_message = session_channel.get_partial_message(SESSION_START_MESSAGE)
    
    async for message in session_channel.history(limit=100):
        if message.id != SESSION_START_MESSAGE:
            try:
                await message.delete()
            except:
                pass

async def shutdown_session_by_user(user: discord.Member):
    """Shutdown session by a user"""
    global session_active, session_start_time, session_starter_id
    
    session_data = load_json(SESSION_FILE)
    
    # Check cooldown
    if session_data.get('start_time'):
        start_time = datetime.fromisoformat(session_data['start_time'])
        elapsed = (datetime.now() - start_time).total_seconds() / 60
        if elapsed < SESSION_SHUTDOWN_COOLDOWN:
            return False, "You are not permitted to shutdown a session unless 15 minutes has elapsed after the session started."
    
    session_active = False
    session_start_time = None
    session_starter_id = None
    
    # Update session status channel
    status_channel = bot.get_channel(SESSION_STATUS_CHANNEL)
    if status_channel:
        await status_channel.edit(name="Sessions: 🔴")
    
    # Save session data
    await save_session_data(False)
    
    # Send shutdown embed
    session_channel = bot.get_channel(SESSION_CHANNEL)
    if session_channel:
        embed = discord.Embed(
            description=f"A session has been shut down by **{user.display_name}**. Thank you for joining today's session. See you soon!",
            color=get_color()
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
        
        await session_channel.send(embed=embed)
    
    # Log to session log channel
    session_log = bot.get_channel(SESSION_LOG_CHANNEL)
    if session_log:
        await session_log.send(embed=discord.Embed(
            title="Session Shutdown",
            description=f"Session shut down by {user.display_name}",
            color=get_color()
        ))
    
    append_log(SESSION_LOG_FILE, f"Session shutdown by {user.display_name} ({user.id})")
    
    return True, "Session shut down successfully."

# ============== COMMANDS ==============

# --- AFK Command ---
@bot.command(name="afk")
async def afk_command(ctx, *, message: str = "AFK"):
    """Set your AFK status"""
    user = ctx.author
    afk_data = load_json(AFK_FILE)
    
    # Add AFK prefix to nickname
    nickname = user.display_name
    if not nickname.startswith("AFK • "):
        try:
            await user.edit(nick=f"AFK • {nickname}")
        except:
            pass
    
    # Save AFK data
    afk_data[str(user.id)] = {
        'name': user.display_name,
        'message': message,
        'mentions': []
    }
    save_json(AFK_FILE, afk_data)
    
    embed = discord.Embed(
        title=f"**{user.display_name}**",
        description=f"> You are now away from your keyboard [AFK] for {message}.\n> Members will be notified about your status.\n> When you are back to your keyboard, you will be shown all the people that mentioned you, while you were AFK.",
        color=get_color()
    )
    
    await ctx.send(embed=embed, delete_after=10)
    append_log(AFK_LOG_FILE, f"AFK set by {user.display_name} ({user.id}): {message}")

@bot.tree.command(name="afk", description="Set your AFK status")
async def afk_slash(interaction: discord.Interaction, *, message: str = "AFK"):
    await interaction.response.defer(ephemeral=True)
    await afk_command(interaction.user, message=message)
    await interaction.followup.send("AFK status set!", ephemeral=True)

# --- DM User Command ---
@bot.command(name="dmuser")
async def dmuser_command(ctx, user: discord.Member, *, message: str):
    """DM a specific user (Executive+ only)"""
    if not is_executive_plus(ctx.author):
        await ctx.send("❌ You don't have permission to use this command.", delete_after=5)
        return
    
    # Create DM embed
    embed = discord.Embed(
        title="<:Offical_server:1475860128686411837> __𝓛𝓐𝓡𝓟 - New Direct Message (DM)__",
        description=f"> From **{ctx.author.display_name}**:\n> {message}\n-# Sent at {datetime.now().strftime('%I:%M%p')}",
        color=get_color()
    )
    
    try:
        await user.send(embed=embed)
        await ctx.send(f"✅ DM sent to {user.display_name}", delete_after=5)
        append_log(DM_LOG_FILE, f"DM to {user.display_name} ({user.id}) by {ctx.author.display_name}: {message}")
    except:
        await ctx.send(f"❌ Could not DM {user.display_name}", delete_after=5)

@bot.tree.command(name="dmuser", description="DM a specific user (Executive+ only)")
@app_commands.describe(user="User to DM", message="Message to send")
async def dmuser_slash(interaction: discord.Interaction, user: discord.Member, message: str):
    if not is_executive_plus(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    # Create DM embed
    embed = discord.Embed(
        title="<:Offical_server:1475860128686411837> __𝓛𝓐𝓡𝓟 - New Direct Message (DM)__",
        description=f"> From **{interaction.user.display_name}**:\n> {message}\n-# Sent at {datetime.now().strftime('%I:%M%p')}",
        color=get_color()
    )
    
    try:
        await user.send(embed=embed)
        await interaction.response.send_message(f"✅ DM sent to {user.display_name}", ephemeral=True)
        append_log(DM_LOG_FILE, f"DM to {user.display_name} ({user.id}) by {interaction.user.display_name}: {message}")
    except:
        await interaction.response.send_message(f"❌ Could not DM {user.display_name}", ephemeral=True)

# --- DM Role Command ---
@bot.command(name="dmrole")
async def dmrole_command(ctx, role: discord.Role, *, message: str):
    """DM all members of a specific role (Foundation+ only)"""
    if not is_foundation_plus(ctx.author):
        await ctx.send("❌ You don't have permission to use this command.", delete_after=5)
        return
    
    # Create DM embed
    embed = discord.Embed(
        title="<:Offical_server:1475860128686411837> __𝓛𝓐𝓡𝓟 - New Direct Message (DM)__",
        description=f"> From **{ctx.author.display_name}**:\n> {message}\n-# Sent at {datetime.now().strftime('%I:%M%p')}",
        color=get_color()
    )
    
    sent_count = 0
    failed_count = 0
    
    for member in ctx.guild.members:
        if role in member.roles:
            try:
                await member.send(embed=embed)
                sent_count += 1
            except:
                failed_count += 1
    
    await ctx.send(f"✅ DM sent to {sent_count} members of {role.name}. Failed: {failed_count}", delete_after=10)
    append_log(DM_LOG_FILE, f"DM to role {role.name} ({role.id}) by {ctx.author.display_name}: {message}")

@bot.tree.command(name="dmrole", description="DM all members of a role (Foundation+ only)")
@app_commands.describe(role="Role to DM", message="Message to send")
async def dmrole_slash(interaction: discord.Interaction, role: discord.Role, message: str):
    if not is_foundation_plus(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    # Create DM embed
    embed = discord.Embed(
        title="<:Offical_server:1475860128686411837> __𝓛𝓐𝓡𝓟 - New Direct Message (DM)__",
        description=f"> From **{interaction.user.display_name}**:\n> {message}\n-# Sent at {datetime.now().strftime('%I:%M%p')}",
        color=get_color()
    )
    
    sent_count = 0
    failed_count = 0
    
    for member in interaction.guild.members:
        if role in member.roles:
            try:
                await member.send(embed=embed)
                sent_count += 1
            except:
                failed_count += 1
    
    await interaction.response.send_message(f"✅ DM sent to {sent_count} members of {role.name}. Failed: {failed_count}", ephemeral=True)
    append_log(DM_LOG_FILE, f"DM to role {role.name} ({role.id}) by {interaction.user.display_name}: {message}")

# --- Session Command ---
@bot.command(name="sessions")
async def sessions_command(ctx, type: str = "private"):
    """Open session management panel"""
    # Check if it's a private session command
    if type.lower() in ["private", "p", "pri", "priv", "priva", "privat"]:
        # Check permissions
        if not is_management_plus(ctx.author):
            await ctx.send("Only Management+ staff members of Los Angeles Roleplay are permitted to manage a session. Refrain from using this command again, unless you become Management.", delete_after=10)
            return
        
        # Check session status
        session_data = load_json(SESSION_FILE)
        session_active = session_data.get('active', False)
        
        # Get status from channel name
        status_channel = bot.get_channel(SESSION_STATUS_CHANNEL)
        session_active = status_channel and "🟢" in status_channel.name
        
        # Create embeds
        embed1 = discord.Embed(color=get_color())
        embed1.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
        
        status_text = "The Session is **currently active**." if session_active else "The Session is **currently inactive**."
        
        options_text = ""
        if session_active:
            options_text = "> - 1. **Boost** the Session.\n> - 2. **Shutdown** the Session.\n> - 3. **Alert** that the Session is full."
        else:
            options_text = "> - 1. Initiate a Session **Vote**.\n> - 2. **Start** a new Session."
        
        embed2 = discord.Embed(
            title="<:Offical_server:1475860128686411837> | Session Management",
            description=f"> Welcome, {ctx.author.mention}. Thanks for opening Los Angeles Roleplay's Session Management panel.\n\n{status_text}\n\nPlease click the options below to manage the session further.\n\n{options_text}",
            color=get_color()
        )
        
        embed3 = discord.Embed(color=get_color())
        embed3.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
        
        # Create view with buttons
        view = SessionManagementView(session_active)
        
        await ctx.send(embeds=[embed1, embed2, embed3], view=view)
        
        # Delete user command
        try:
            await ctx.message.delete()
        except:
            pass
    else:
        await ctx.send("Usage: <sessions private", delete_after=5)

@bot.tree.command(name="sessions", description="Open session management panel")
async def sessions_slash(interaction: discord.Interaction):
    # Check permissions
    if not is_management_plus(interaction.user):
        await interaction.response.send_message(
            "Only Management+ staff members of Los Angeles Roleplay are permitted to manage a session. Refrain from using this command again, unless you become Management.",
            ephemeral=True
        )
        return
    
    # Check session status
    session_data = load_json(SESSION_FILE)
    session_active = session_data.get('active', False)
    
    # Get status from channel name
    status_channel = bot.get_channel(SESSION_STATUS_CHANNEL)
    session_active = status_channel and "🟢" in status_channel.name
    
    # Create embeds
    embed1 = discord.Embed(color=get_color())
    embed1.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
    
    status_text = "The Session is **currently active**." if session_active else "The Session is **currently inactive**."
    
    options_text = ""
    if session_active:
        options_text = "> - 1. **Boost** the Session.\n> - 2. **Shutdown** the Session.\n> - 3. **Alert** that the Session is full."
    else:
        options_text = "> - 1. Initiate a Session **Vote**.\n> - 2. **Start** a new Session."
    
    embed2 = discord.Embed(
        title="<:Offical_server:1475860128686411837> | Session Management",
        description=f"> Welcome, {interaction.user.mention}. Thanks for opening Los Angeles Roleplay's Session Management panel.\n\n{status_text}\n\nPlease click the options below to manage the session further.\n\n{options_text}",
        color=get_color()
    )
    
    embed3 = discord.Embed(color=get_color())
    embed3.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
    
    # Create view with buttons
    view = SessionManagementView(session_active)
    
    await interaction.response.send_message(embeds=[embed1, embed2, embed3], view=view)

# --- Session Button Callbacks ---
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or not interaction.data.get('custom_id'):
        return
    
    custom_id = interaction.data['custom_id']
    user = interaction.user
    
    # Check permissions for session actions
    if custom_id.startswith("session_") and not is_management_plus(user):
        await interaction.response.send_message(
            "Only Management+ staff members of Los Angeles Roleplay are permitted to manage a session.",
            ephemeral=True
        )
        return
    
    if custom_id == "session_boost":
        await handle_session_boost(interaction, user)
    elif custom_id == "session_shutdown":
        await handle_session_shutdown(interaction, user)
    elif custom_id == "session_full":
        await handle_session_full(interaction, user)
    elif custom_id == "session_vote":
        await handle_session_vote_start(interaction, user)
    elif custom_id == "session_start":
        await handle_session_start(interaction, user)

async def handle_session_boost(interaction: discord.Interaction, user: discord.Member):
    """Handle session boost"""
    session_channel = bot.get_channel(SESSION_CHANNEL)
    if not session_channel:
        return
    
    # Cleanup channel
    await cleanup_session_channel()
    
    # Send session low embed
    embed1 = discord.Embed(color=get_color())
    embed1.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
    
    session_ping = interaction.guild.get_role(SESSION_PING_ROLE).mention if interaction.guild.get_role(SESSION_PING_ROLE) else "@here"
    
    embed2 = discord.Embed(
        description=f"@here, {session_ping}\nThe session is currently running **low** on players. Please join up to ensure that the server can be full!",
        color=get_color()
    )
    embed2.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
    
    await session_channel.send(embeds=[embed1, embed2])
    await interaction.response.send_message("Session has been boosted!", ephemeral=True)
    
    append_log(SESSION_LOG_FILE, f"Session boosted by {user.display_name}")

async def handle_session_shutdown(interaction: discord.Interaction, user: discord.Member):
    """Handle session shutdown"""
    session_data = load_json(SESSION_FILE)
    
    # Check cooldown
    if session_data.get('start_time'):
        start_time = datetime.fromisoformat(session_data['start_time'])
        elapsed = (datetime.now() - start_time).total_seconds() / 60
        if elapsed < SESSION_SHUTDOWN_COOLDOWN:
            await interaction.response.send_message(
                "You are not permitted to shutdown a session unless 15 minutes has elapsed after the session started.",
                ephemeral=True
            )
            return
    
    success, message = await shutdown_session_by_user(user)
    await interaction.response.send_message(message, ephemeral=True)

async def handle_session_full(interaction: discord.Interaction, user: discord.Member):
    """Handle session full notification"""
    session_channel = bot.get_channel(SESSION_CHANNEL)
    if not session_channel:
        return
    
    await session_channel.send("The session has officially become full. Thank you so much for bringing up activity! There may be a queue in Los Angeles Roleplay.")
    await interaction.response.send_message("Session full notification sent!", ephemeral=True)
    
    append_log(SESSION_LOG_FILE, f"Session full notification by {user.display_name}")

async def handle_session_vote_start(interaction: discord.Interaction, user: discord.Member):
    """Handle session vote start - ask for vote threshold"""
    await interaction.response.send_modal(SessionVoteModal())

async def handle_session_start(interaction: discord.Interaction, user: discord.Member):
    """Handle direct session start"""
    global session_active, session_start_time, session_starter_id
    
    # Update session status channel
    status_channel = bot.get_channel(SESSION_STATUS_CHANNEL)
    if status_channel:
        await status_channel.edit(name="Sessions: 🟢")
    
    # Save session data
    await save_session_data(True, user.id)
    session_active = True
    session_start_time = datetime.now()
    session_starter_id = user.id
    
    # Send session start embed
    session_channel = bot.get_channel(SESSION_CHANNEL)
    if session_channel:
        # Cleanup channel first
        await cleanup_session_channel()
        
        embed1 = discord.Embed(color=get_color())
        embed1.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
        
        embed2 = discord.Embed(
            title="<:Offical_server:1475860128686411837> | 𝓛𝓐𝓡𝓟 Session Started",
            description=f"After a session has begun in Los Angeles Roleplay. Please refer below for more information.\n- In-Game Code: L",
            color=get_color()
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
        
        session_ping = interaction.guild.get_role(SESSION_PING_ROLE).mention if interaction.guild.get_role(SESSION_PING_ROLE) else ""
        await session_channel.send(content=session_ping, embeds=[embed1, embed2])
    
    # Log to session log channel
    session_log = bot.get_channel(SESSION_LOG_CHANNEL)
    if session_log:
        await session_log.send(embed=discord.Embed(
            title="Session Started",
            description=f"Session started by {user.display_name}",
            color=get_color()
        ))
    
    append_log(SESSION_LOG_FILE, f"Session started by {user.display_name} ({user.id})")
    
    await interaction.response.send_message("Session has been started!", ephemeral=True)

# --- Session Vote Modal ---
class SessionVoteModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Session Vote")
        
        self.vote_threshold = discord.ui.TextInput(
            label="Vote Threshold",
            placeholder="How many votes needed to start?",
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.vote_threshold)
    
    async def callback(self, interaction: discord.Interaction):
        try:
            threshold = int(self.vote_threshold.value)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
            return
        
        # Start the vote
        await start_session_vote(interaction, interaction.user, threshold)

async def start_session_vote(interaction: discord.Interaction, user: discord.Member, threshold: int):
    """Start a session vote"""
    global vote_threshold, vote_message_id
    
    # Send vote to staff chat
    staff_channel = bot.get_channel(STAFF_CHAT)
    if staff_channel:
        await staff_channel.send(
            f"{user.mention}: The Session Vote has received `✅/0/{threshold}`. Would you like to begin the session?"
        )
    
    # Create vote embed in session channel
    session_channel = bot.get_channel(SESSION_CHANNEL)
    if session_channel:
        # Cleanup channel first
        await cleanup_session_channel()
        
        embed1 = discord.Embed(color=get_color())
        embed1.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
        
        embed2 = discord.Embed(
            title="<:Offical_server:1475860128686411837> | 𝓛𝓐𝓡𝓟 Session Voting",
            description=f"> A session voting has been started by {user.display_name}.\n> - If you would like the session to start, please react below with <:Checkmark:1480018743714386070>. Once the session reaches {threshold}, the session will begin.\n> - Votes: 0/{threshold}",
            color=get_color()
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
        
        session_ping = interaction.guild.get_role(SESSION_PING_ROLE).mention if interaction.guild.get_role(SESSION_PING_ROLE) else ""
        vote_message = await session_channel.send(content=session_ping, embeds=[embed1, embed2])
        
        # Self react with checkmark
        await vote_message.add_reaction("✅")
        
        vote_message_id = vote_message.id
        vote_threshold = threshold
        
        # Store vote data
        session_data = load_json(SESSION_FILE)
        session_data['vote_message_id'] = vote_message_id
        session_data['vote_threshold'] = threshold
        session_data['vote_initiator'] = user.id
        session_data['vote_count'] = 0
        session_data['vote_active'] = True
        save_json(SESSION_FILE, session_data)
        
        append_log(SESSION_LOG_FILE, f"Session vote started by {user.display_name} with threshold {threshold}")
    
    await interaction.response.send_message("Session vote has been initiated!", ephemeral=True)

# --- Vote Reaction Handler ---
@bot.event
async def on_raw_reaction_add(payload):
    if payload.message_id != vote_message_id:
        return
    
    if str(payload.emoji) != "✅":
        return
    
    # Get vote data
    session_data = load_json(SESSION_FILE)
    if not session_data.get('vote_active', False):
        return
    
    # Get the message
    channel = bot.get_channel(SESSION_CHANNEL)
    if not channel:
        return
    
    try:
        message = await channel.fetch_message(vote_message_id)
    except:
        return
    
    # Count reactions (excluding bot's own reaction)
    vote_count = sum(1 for r in message.reactions if str(r.emoji) == "✅")
    vote_count -= 1  # Subtract bot's own reaction
    
    threshold = session_data.get('vote_threshold', 5)
    
    # Update vote count
    session_data['vote_count'] = vote_count
    save_json(SESSION_FILE, session_data)
    
    # Update embed
    embed2 = discord.Embed(
        title="<:Offical_server:1475860128686411837> | 𝓛𝓐𝓡𝓟 Session Voting",
        description=f"> A session voting has been started by <@{session_data.get('vote_initiator')}>.\n> - If you would like the session to start, please react below with <:Checkmark:1480018743714386070>. Once the session reaches {threshold}, the session will begin.\n> - Votes: {vote_count}/{threshold}",
        color=get_color()
    )
    embed2.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
    
    await message.edit(embeds=[message.embeds[0], embed2])
    
    # Check if threshold reached
    if vote_count >= threshold:
        # Start the session
        guild = bot.get_guild(GUILD_ID)
        initiator = guild.get_member(session_data.get('vote_initiator'))
        
        if initiator:
            await handle_session_start_from_vote(initiator)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.message_id != vote_message_id:
        return
    
    if str(payload.emoji) != "✅":
        return
    
    # Re-add the bot's reaction if it was removed
    channel = bot.get_channel(SESSION_CHANNEL)
    if not channel:
        return
    
    try:
        message = await channel.fetch_message(vote_message_id)
    except:
        return
    
    # Check if bot reaction is still there
    bot_reacted = any(r.emoji == "✅" and r.me for r in message.reactions)
    
    if not bot_reacted:
        await message.add_reaction("✅")

async def handle_session_start_from_vote(user: discord.Member):
    """Start session after vote threshold reached"""
    global session_active, session_start_time, session_starter_id
    
    # Update session status channel
    status_channel = bot.get_channel(SESSION_STATUS_CHANNEL)
    if status_channel:
        await status_channel.edit(name="Sessions: 🟢")
    
    # Save session data
    await save_session_data(True, user.id)
    session_active = True
    session_start_time = datetime.now()
    session_starter_id = user.id
    
    # Get session data for vote info
    session_data = load_json(SESSION_FILE)
    session_data['vote_active'] = False
    save_json(SESSION_FILE, session_data)
    
    # Send session start embed
    session_channel = bot.get_channel(SESSION_CHANNEL)
    if session_channel:
        embed1 = discord.Embed(color=get_color())
        embed1.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
        
        embed2 = discord.Embed(
            title="<:Offical_server:1475860128686411837> | 𝓛𝓐𝓡𝓟 Session Voting",
            description=f"After {session_data.get('vote_threshold', 5)} votes have been received, a session has begun in Los Angeles Roleplay. Please refer below for more information.\n- In-Game Code: L",
            color=get_color()
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
        
        session_ping = session_channel.guild.get_role(SESSION_PING_ROLE).mention if session_channel.guild.get_role(SESSION_PING_ROLE) else ""
        await session_channel.send(content=session_ping, embeds=[embed1, embed2])
    
    # Log to session log channel
    session_log = bot.get_channel(SESSION_LOG_CHANNEL)
    if session_log:
        await session_log.send(embed=discord.Embed(
            title="Session Started via Vote",
            description=f"Session started by {user.display_name} after vote threshold reached",
            color=get_color()
        ))
    
    append_log(SESSION_LOG_FILE, f"Session started via vote by {user.display_name} ({user.id})")

# ============== RUN BOT ==============
if __name__ == "__main__":
    # Get token from environment variable
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not TOKEN:
        logger.error("Please set DISCORD_BOT_TOKEN environment variable")
        exit(1)
    
    bot.run(TOKEN)

