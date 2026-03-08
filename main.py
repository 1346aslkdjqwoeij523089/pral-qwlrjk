import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from flask import Flask
from threading import Thread

import requests
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

# Flask app for keeping bot online
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Run Flask in background
flask_thread = Thread(target=run_flask, daemon=True)
flask_thread.start()

# Bot Configuration
GUILD_ID = 1464682632204779602
SIDEBAR_COLOR = 0x004bae
BOT_PREFIX = "<"

# Staff Role IDs
ROLES = {
    "FOUNDATION": 1464682632754233539,
    "EXECUTIVE_COUNCIL": 1466490625259212821,
    "MANAGEMENT": 1464682632754233535,
    "HIGH_RANKING": 1464682632729071818,
    "INTERNAL_AFFAIRS": 1464682632661958858,
    "ADMINISTRATION": 1464682632661958852,
    "MODERATION": 1464682632645185848,
    "STAFF": 1464682632645185843,
    "BOT_DEV": 1479003906531917886
}

# Channel IDs
CHANNELS = {
    "WELCOME": 1464682633371062293,
    "MEMBER_COUNT_VC": 1471478613038600328,
    "SESSION_CHANNEL": 1464682633559801939,
    "SESSION_INFO": 1480024519677706382,
    "SESSION_VC_STATUS": 1480013219199451308,
    "STAFF_CHAT": 1464682633853407327,
    "LOG_CHANNEL": 1480026203443171338,
    "SESSION_PING": 1465771610312278180
}

# ER:LC Role
ERLC_STAFF_ROLE = 1465722596694818891

# Session vote emoji
VOTE_EMOJI = "✅"

# Intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Bot setup
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

# Use bot.tree directly instead of creating a new CommandTree
tree = bot.tree

# Global data storage
session_data = {
    "active": False,
    "started_at": None,
    "started_by": None,
    "vote_threshold": None,
    "vote_message_id": None,
    "session_message_id": None,
    "last_reminder": None
}

afk_data = {}
mentions_while_afk = {}

# Helper functions
def get_color():
    return SIDEBAR_COLOR

def check_executive_plus():
    async def predicate(interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        exec_role = guild.get_role(ROLES["EXECUTIVE_COUNCIL"])
        bot_dev_role = guild.get_role(ROLES["BOT_DEV"])
        return exec_role in member.roles or bot_dev_role in member.roles
    return app_commands.check(predicate)

def check_management_plus():
    async def predicate(interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        management_role = guild.get_role(ROLES["MANAGEMENT"])
        exec_role = guild.get_role(ROLES["EXECUTIVE_COUNCIL"])
        bot_dev_role = guild.get_role(ROLES["BOT_DEV"])
        return management_role in member.roles or exec_role in member.roles or bot_dev_role in member.roles
    return app_commands.check(predicate)

def check_foundation_plus():
    async def predicate(interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        foundation_role = guild.get_role(ROLES["FOUNDATION"])
        bot_dev_role = guild.get_role(ROLES["BOT_DEV"])
        return foundation_role in member.roles or bot_dev_role in member.roles
    return app_commands.check(predicate)

def check_staff():
    async def predicate(interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        staff_roles = [
            ROLES["FOUNDATION"], ROLES["EXECUTIVE_COUNCIL"], 
            ROLES["MANAGEMENT"], ROLES["HIGH_RANKING"],
            ROLES["INTERNAL_AFFAIRS"], ROLES["ADMINISTRATION"],
            ROLES["MODERATION"], ROLES["STAFF"], ROLES["BOT_DEV"]
        ]
        return any(role in member.roles for role in staff_roles)
    return app_commands.check(predicate)

def get_erlc_data():
    """Get ER:LC server data from API"""
    api_key = os.environ.get("ERLC_API_KEY", "")
    if not api_key:
        return {"players": 0, "max_players": 39, "server_code": "N/A"}
    
    try:
        # This is a placeholder - adjust based on actual ER:LC API
        response = requests.get(
            f"https://api.erlcenter.com/v1/server/status",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return {
                "players": data.get("player_count", 0),
                "max_players": 39,
                "server_code": data.get("server_code", "N/A")
            }
    except:
        pass
    
    return {"players": 0, "max_players": 39, "server_code": "N/A"}

def log_to_channel(guild, action: str, details: str, user: discord.Member = None):
    """Log actions to the log channel"""
    log_channel = guild.get_channel(CHANNELS["LOG_CHANNEL"])
    if not log_channel:
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    embed = discord.Embed(
        description=f"**{action}**\n{details}",
        color=get_color()
    )
    embed.set_footer(text=f"{timestamp}")
    if user:
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)
    
    asyncio.create_task(log_channel.send(embed=embed))

# Flask health check
def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# Tasks
@tasks.loop(minutes=15)
async def update_member_count():
    """Update the member count voice channel every 15 minutes"""
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    
    vc = guild.get_channel(CHANNELS["MEMBER_COUNT_VC"])
    if not vc:
        return
    
    # Count members excluding bots
    member_count = len([m for m in guild.members if not m.bot])
    
    try:
        await vc.edit(name=f"Members: {member_count}")
        logger.info(f"Updated member count to {member_count}")
    except Exception as e:
        logger.error(f"Failed to update member count: {e}")

# Events
@bot.event
async def on_ready():
    """Bot ready event"""
    logger.info(f"Bot logged in as {bot.user}")
    
    # Sync commands
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    logger.info("Commands synced")
    
    # Start tasks
    update_member_count.start()
    session_reminder_task.start()

    # Set initial session status
    await update_session_status()

@bot.event
async def on_member_join(member):
    """Welcome new members"""
    guild = member.guild
    welcome_channel = guild.get_channel(CHANNELS["WELCOME"])
    
    if not welcome_channel:
        return
    
    embed = discord.Embed(color=get_color())
    embed.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479260063192584273/welcomelarp.png?ex=69ae06ca&is=69acb54a&hm=e3cf31d81d9dee35659908000b6d6ad4c2cc9831e57c719cac8c7a6e8d7bfc85&")
    
    await welcome_channel.send(f"{member.mention}", embed=embed)

@bot.event
async def on_message(message):
    """Handle messages for AFK system"""
    # Skip bot messages
    if message.author.bot:
        return
    
    # Check if author is AFK
    if message.author.id in afk_data:
        afk_info = afk_data.pop(message.author.id)
        mentions = mentions_while_afk.pop(message.author.id, [])
        
        # Remove AFK prefix from nickname
        if message.author.nickname and message.author.nickname.startswith("AFK • "):
            try:
                await message.author.edit(nickname=message.author.nickname.replace("AFK • ", ""))
            except:
                pass
        
        # Show who mentioned them while AFK
        embed = discord.Embed(
            title="Welcome back!",
            description=f"You are now back from AFK.",
            color=get_color()
        )
        
        if mentions:
            mention_text = ", ".join([str(m) for m in mentions])
            embed.add_field(name="While you were away, you were mentioned by:", value=mention_text, inline=False)
        
        await message.author.send(embed=embed)
    
    # Check for AFK mentions
    for mention in message.mentions:
        if mention.id in afk_data:
            afk_info = afk_data[mention.id]
            if mention.id not in mentions_while_afk:
                mentions_while_afk[mention.id] = []
            mentions_while_afk[mention.id].append(message.author)
            
            await message.reply(f"{mention.nickname} is currently AFK {afk_info['reason']}")

    await bot.process_commands(message)

async def update_session_status():
    """Update session status channel name"""
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    
    session_vc = guild.get_channel(CHANNELS["SESSION_VC_STATUS"])
    if not session_vc:
        return
    
    if session_data["active"]:
        await session_vc.edit(name="Sessions: 🟢")
    else:
        await session_vc.edit(name="Sessions: 🔴")

async def cleanup_session_channel():
    """Delete messages in session channel except specific ones"""
    guild = bot.get_guild(GUILD_ID)
    channel = guild.get_channel(CHANNELS["SESSION_CHANNEL"])
    
    if not channel:
        return
    
    keep_message_id = 1480023088799416451
    
    async for message in channel.history(limit=100):
        if message.id != keep_message_id and not message.pinned:
            try:
                await message.delete()
            except:
                pass

async def send_session_log(guild, action: str, details: str):
    """Send session action logs to the session channel"""
    channel = guild.get_channel(CHANNELS["SESSION_CHANNEL"])
    if not channel:
        return
    
    embed = discord.Embed(description=f"**{action}**\n{details}", color=get_color())
    embed.set_footer(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    await channel.send(embed=embed)

# Slash Commands
@tree.command(name="afk", description="Set your AFK status", guild=discord.Object(id=GUILD_ID))
async def afk_command(interaction: discord.Interaction, *, message: str = "AFK"):
    """Set AFK status"""
    user = interaction.user
    guild = interaction.guild
    
    # Store AFK data
    afk_data[user.id] = {"reason": message, "started_at": datetime.now()}
    
    # Add AFK prefix to nickname
    if user.nickname:
        if not user.nickname.startswith("AFK • "):
            try:
                await user.edit(nickname=f"AFK • {user.nickname}")
            except:
                pass
    else:
        try:
            await user.edit(nickname=f"AFK • {user.name}")
        except:
            pass
    
    embed = discord.Embed(
        description=f"**{user.nickname}**\n> You are now away from your keyboard [AFK] for {message}.\n> Members will be notified about your status.\n> When you are back to your keyboard, you will be shown all the people that mentioned you, while you were AFK.",
        color=get_color()
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="dmuser", description="DM a specific user", guild=discord.Object(id=GUILD_ID))
@check_executive_plus()
async def dmuser_command(interaction: discord.Interaction, user: discord.User, *, message: str):
    """DM a specific user"""
    guild = interaction.guild
    member = guild.get_member(user.id) or user
    
    # Create DM embed
    member_nickname = guild.get_member(interaction.user.id).nickname or interaction.user.name
    
    embed = discord.Embed(color=get_color())
    embed.set_author(name="𝓛𝓐𝓡𝓟 - New Direct Message (DM)", icon_url=guild.icon.url if guild.icon else None)
    embed.description = f"> From **{member_nickname}**:\n> {message}\n-# Sent at {datetime.now().strftime('%I:%M%p')}"
    embed.set_footer(text="Los Angeles Roleplay")
    
    try:
        await member.send(embed=embed)
        await interaction.response.send_message(f"Successfully sent DM to {user.mention}", ephemeral=True)
        
        # Log to channel
        log_to_channel(guild, "DM User", f"Sent to: {user}\nMessage: {message}", interaction.user)
    except:
        await interaction.response.send_message(f"Failed to send DM to {user.mention}", ephemeral=True)

@tree.command(name="dmrole", description="DM a specific role", guild=discord.Object(id=GUILD_ID))
@check_foundation_plus()
async def dmrole_command(interaction: discord.Interaction, role: discord.Role, *, message: str):
    """DM all members with a specific role"""
    guild = interaction.guild
    member_nickname = interaction.user.nickname or interaction.user.name
    
    sent_count = 0
    failed_count = 0
    
    for member in role.members:
        # Create DM embed
        embed = discord.Embed(color=get_color())
        embed.set_author(name="𝓛𝓐𝓟 - New Direct Message (DM)", icon_url=guild.icon.url if guild.icon else None)
        embed.description = f"> From **{member_nickname}**:\n> {message}\n-# Sent at {datetime.now().strftime('%I:%M%p')}"
        embed.set_footer(text="Los Angeles Roleplay")
        
        try:
            await member.send(embed=embed)
            sent_count += 1
        except:
            failed_count += 1
    
    await interaction.response.send_message(f"DM sent to {sent_count} members. Failed: {failed_count}", ephemeral=True)
    
    # Log to channel
    log_to_channel(guild, "DM Role", f"Role: {role.name}\nSent to: {sent_count} members\nMessage: {message}", interaction.user)

@tree.command(name="warn", description="Warn a member", guild=discord.Object(id=GUILD_ID))
@check_staff()
async def warn_command(interaction: discord.Interaction, member: discord.Member, *, reason: str):
    """Warn a member"""
    guild = interaction.guild
    
    embed = discord.Embed(
        title="Warning",
        description=f"You have been warned in Los Angeles Roleplay",
        color=get_color()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Warned by", value=interaction.user.mention, inline=False)
    
    try:
        await member.send(embed=embed)
    except:
        pass
    
    await interaction.response.send_message(f"Warning sent to {member.mention}", ephemeral=True)
    
    # Log
    log_to_channel(guild, "Warn", f"Member: {member}\nReason: {reason}", interaction.user)

@tree.command(name="kick", description="Kick a member", guild=discord.Object(id=GUILD_ID))
@check_staff()
async def kick_command(interaction: discord.Interaction, member: discord.Member, *, reason: str):
    """Kick a member"""
    guild = interaction.guild
    
    try:
        await member.kick(reason=f"By: {interaction.user} | Reason: {reason}")
        await interaction.response.send_message(f"Kicked {member.mention}", ephemeral=True)
        
        # Log
        log_to_channel(guild, "Kick", f"Member: {member}\nReason: {reason}", interaction.user)
    except Exception as e:
        await interaction.response.send_message(f"Failed to kick: {e}", ephemeral=True)

@tree.command(name="ban", description="Ban a member", guild=discord.Object(id=GUILD_ID))
@check_staff()
async def ban_command(interaction: discord.Interaction, member: discord.Member, *, reason: str):
    """Ban a member"""
    guild = interaction.guild
    
    try:
        await member.ban(reason=f"By: {interaction.user} | Reason: {reason}")
        await interaction.response.send_message(f"Banned {member.mention}", ephemeral=True)
        
        # Log
        log_to_channel(guild, "Ban", f"Member: {member}\nReason: {reason}", interaction.user)
    except Exception as e:
        await interaction.response.send_message(f"Failed to ban: {e}", ephemeral=True)

@tree.command(name="timeout", description="Timeout/Mute a member", guild=discord.Object(id=GUILD_ID))
@tree.command(name="mute", description="Mute a member", guild=discord.Object(id=GUILD_ID))
@check_staff()
async def timeout_command(interaction: discord.Interaction, member: discord.Member, duration: int, *, reason: str):
    """Timeout/Mute a member"""
    guild = interaction.guild
    
    until = datetime.now() + timedelta(minutes=duration)
    
    try:
        await member.timeout(until, reason=reason)
        await interaction.response.send_message(f"Timed out {member.mention} for {duration} minutes", ephemeral=True)
        
        # Log
        log_to_channel(guild, "Timeout", f"Member: {member}\nDuration: {duration} minutes\nReason: {reason}", interaction.user)
    except Exception as e:
        await interaction.response.send_message(f"Failed to timeout: {e}", ephemeral=True)

@tree.command(name="sessions", description="Session Management Panel", guild=discord.Object(id=GUILD_ID))
async def sessions_command(interaction: discord.Interaction):
    """Session Management Panel"""
    guild = interaction.guild
    
    # Check if command is sent privately
    is_private = interaction.command.name in ["sessions", "s", "se", "ses", "sess", "sessi", "session", "sessions"] and False  # This is handled by checking option
    
    # Check permissions
    management_role = guild.get_role(ROLES["MANAGEMENT"])
    exec_role = guild.get_role(ROLES["EXECUTIVE_COUNCIL"])
    bot_dev_role = guild.get_role(ROLES["BOT_DEV"])
    
    member = interaction.user
    if not (management_role in member.roles or exec_role in member.roles or bot_dev_role in member.roles):
        embed = discord.Embed(
            description="Only Management+ staff members of Los Angeles Roleplay are permitted to manage a session. Refrain from using this command again, unless you become Management.",
            color=get_color()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Get session status
    session_vc = guild.get_channel(CHANNELS["SESSION_VC_STATUS"])
    is_active = session_data["active"]
    
    session_status = "The Session is **currently active**." if is_active else "The Session is **currently inactive**."
    if session_vc:
        if "🟢" in session_vc.name:
            session_status = "The Session is **currently active**."
        elif "🔴" in session_vc.name:
            session_status = "The Session is **currently inactive**."
    
    # Get ER:LC data
    erlc_data = get_erlc_data()
    erlc_staff_role = guild.get_role(ERLC_STAFF_ROLE)
    staff_count = len([m for m in guild.members if erlc_staff_role in m.roles]) if erlc_staff_role else 0
    
    # Build options based on session status
    options = []
    if is_active:
        options = [
            discord.SelectOption(label="Session Boost", description="Boost the session", emoji="⬆️"),
            discord.SelectOption(label="Session Shutdown", description="Shutdown the session", emoji="⏹️"),
            discord.SelectOption(label="Session Full", description="Alert that session is full", emoji="✅")
        ]
    else:
        options = [
            discord.SelectOption(label="Session Vote", description="Initiate a session vote", emoji="🗳️"),
            discord.SelectOption(label="Start Session", description="Start a new session", emoji="▶️")
        ]
    
    # Create the session panel
    view = SessionView(is_active, session_data)
    
    embed = discord.Embed(color=get_color())
    embed.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
    
    embed2 = discord.Embed(
        title="<:Offical_server:1475860128686411837> | Session Management",
        description=f"Welcome, {interaction.user.mention}. Thanks for opening Los Angeles Roleplay's Session Management panel.\n\n{session_status}\n\n**In-Game Code:** {erlc_data['server_code']}\n**Players:** {erlc_data['players']}/{erlc_data['max_players']}\n**Staff On-Duty:** {staff_count}",
        color=get_color()
    )
    
    if is_active:
        embed2.description += "\n\n> - 1. **Boost** the Session.\n> - 2. **Shutdown** the Session.\n> - 3. **Alert** that the Session is full."
    else:
        embed2.description += "\n\n> - 1. Initiate a Session **Vote**.\n> - 2. **Start** a new Session."
    
    embed2.set_footer(text="Los Angeles Roleplay", icon_url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
    
    # Send embeds
    await interaction.response.send_message(embeds=[embed, embed2], view=view, ephemeral=True)

class SessionView(discord.ui.View):
    def __init__(self, is_active: bool, session_info: dict):
        super().__init__(timeout=None)
        self.is_active = is_active
        self.session_info = session_info
        
        options = []
        if is_active:
            options = [
                discord.SelectOption(label="Session Boost", value="boost", description="Boost the session", emoji="⬆️"),
                discord.SelectOption(label="Session Shutdown", value="shutdown", description="Shutdown the session", emoji="⏹️"),
                discord.SelectOption(label="Session Full", value="full", description="Alert that session is full", emoji="✅")
            ]
        else:
            options = [
                discord.SelectOption(label="Session Vote", value="vote", description="Initiate a session vote", emoji="🗳️"),
                discord.SelectOption(label="Start Session", value="start", description="Start a new session", emoji="▶️")
            ]
        
        select = discord.ui.Select(placeholder="Select an option...", options=options)
        select.callback = self.session_callback
        self.add_item(select)
    
    async def session_callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        choice = interaction.data.get("values", [None])[0]
        
        if choice == "vote":
            # Show modal for vote threshold
            modal = VoteThresholdModal()
            await interaction.response.send_modal(modal)
        
        elif choice == "start":
            # Start session directly
            await start_session(interaction.user, guild)
            await interaction.response.send_message("Session started!", ephemeral=True)
        
        elif choice == "boost":
            await send_session_log(guild, "Session Boost", "The session has been boosted!")
            await interaction.response.send_message("Session boosted!", ephemeral=True)
        
        elif choice == "shutdown":
            # Check 15 minute cooldown
            if session_data["started_at"]:
                elapsed = datetime.now() - session_data["started_at"]
                if elapsed < timedelta(minutes=15):
                    await interaction.response.send_message("You are not permitted to shutdown a session unless 15 minutes has elapsed after the session started.", ephemeral=True)
                    return
            
            await shutdown_session(interaction.user, guild)
            await interaction.response.send_message("Session shutdown!", ephemeral=True)
        
        elif choice == "full":
            session_channel = guild.get_channel(CHANNELS["SESSION_CHANNEL"])
            if session_channel:
                await session_channel.send("The session has officially become full. Thank you so much for bringing up activity! There may be a queue in Los Angeles Roleplay.")
            await interaction.response.send_message("Session full message sent!", ephemeral=True)

class VoteThresholdModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Session Vote Threshold")
        self.vote_count = discord.ui.TextInput(
            label="How many votes?",
            placeholder="Enter number of votes needed",
            required=True
        )
        self.add_item(self.vote_count)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            threshold = int(self.vote_count.value)
            guild = interaction.guild
            
            # Create vote embed
            embed = discord.Embed(color=get_color())
            embed.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
            
            embed2 = discord.Embed(
                title="<:Offical_server:1475860128686411837> | 𝓛𝓐𝓡𝓟 Session Voting",
                description=f"A session voting has been started by {interaction.user.nickname or interaction.user.name}.\n\n- If you would like the session to start, please react below with {VOTE_EMOJI}. Once the session reaches {threshold}, the session will begin.\n\n- Votes: 0/{threshold}",
                color=get_color()
            )
            embed2.set_footer(text="Los Angeles Roleplay", icon_url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
            
            # Send to session channel
            session_channel = guild.get_channel(CHANNELS["SESSION_CHANNEL"])
            
            # Cleanup first
            await cleanup_session_channel()
            
            # Send vote message
            vote_message = await session_channel.send(embeds=[embed, embed2])
            await vote_message.add_reaction(VOTE_EMOJI)
            
            # Store vote data
            session_data["vote_threshold"] = threshold
            session_data["vote_message_id"] = vote_message.id
            session_data["vote_started_by"] = interaction.user.id
            
            # Notify in staff chat
            staff_channel = guild.get_channel(CHANNELS["STAFF_CHAT"])
            if staff_channel:
                session_ping = guild.get_role(CHANNELS["SESSION_PING"])
                await staff_channel.send(f"{interaction.user.mention}: The Session Vote has received `0/{VOTE_EMOJI}. Would you like to begin the session?")
            
            await interaction.response.send_message("Session vote started!", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("Please enter a valid number!", ephemeral=True)

async def start_session(starter: discord.Member, guild: discord.Guild):
    """Start a session"""
    session_data["active"] = True
    session_data["started_at"] = datetime.now()
    session_data["started_by"] = starter.id
    session_data["last_reminder"] = datetime.now()
    
    # Update channel name
    session_vc = guild.get_channel(CHANNELS["SESSION_VC_STATUS"])
    if session_vc:
        await session_vc.edit(name="Sessions: 🟢")
    
    # Get ER:LC data
    erlc_data = get_erlc_data()
    erlc_staff_role = guild.get_role(ERLC_STAFF_ROLE)
    staff_count = len([m for m in guild.members if erlc_staff_role in m.roles]) if erlc_staff_role else 0
    
    # Send session start embed
    session_channel = guild.get_channel(CHANNELS["SESSION_CHANNEL"])
    if session_channel:
        # Cleanup first
        await cleanup_session_channel()
        
        embed = discord.Embed(color=get_color())
        embed.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
        
        embed2 = discord.Embed(
            title="<:Offical_server:1475860128686411837> | 𝓛𝓐𝓡𝓟 Session Voting",
            description=f"After the required vote threshold has been received, a session has begun in Los Angeles Roleplay. Please refer below for more information.\n\n**In-Game Code:** {erlc_data['server_code']}\n**Players:** {erlc_data['players']}/{erlc_data['max_players']}\n**Staff On-Duty:** {staff_count}",
            color=get_color()
        )
        embed2.set_footer(text="Los Angeles Roleplay", icon_url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
        
        msg = await session_channel.send(embeds=[embed, embed2])
        session_data["session_message_id"] = msg.id
    
    # Save session info to file
    await save_session_info()
    
    # Log
    log_to_channel(guild, "Session Started", f"Started by: {starter}", starter)

async def shutdown_session(shutdownter: discord.Member, guild: discord.Guild):
    """Shutdown a session"""
    session_data["active"] = False
    session_data["started_at"] = None
    session_data["started_by"] = None
    
    # Update channel name
    session_vc = guild.get_channel(CHANNELS["SESSION_VC_STATUS"])
    if session_vc:
        await session_vc.edit(name="Sessions: 🔴")
    
    # Send shutdown embed
    session_channel = guild.get_channel(CHANNELS["SESSION_CHANNEL"])
    if session_channel:
        embed = discord.Embed(
            description=f"A session has been shut down by **{shutdownter.nickname or shutdownter.name}**. Thank you for joining today's session. See you soon!",
            color=get_color()
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
        
        await session_channel.send(embed=embed)
    
    # Clear vote data
    session_data["vote_threshold"] = None
    session_data["vote_message_id"] = None
    
    # Save session info to file
    await save_session_info()
    
    # Log
    log_to_channel(guild, "Session Shutdown", f"Shutdown by: {shutdownter}", shutdownter)

async def save_session_info():
    """Save session info to file for persistence"""
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    
    # Get ER:LC data
    erlc_data = get_erlc_data()
    erlc_staff_role = guild.get_role(ERLC_STAFF_ROLE)
    staff_count = len([m for m in guild.members if erlc_staff_role in m.roles]) if erlc_staff_role else 0
    
    session_info = {
        "active": session_data["active"],
        "started_at": session_data["started_at"].isoformat() if session_data["started_at"] else None,
        "started_by": session_data["started_by"],
        "players": erlc_data["players"],
        "staff_on_duty": staff_count,
        "timestamp": datetime.now().isoformat()
    }
    
    # Save to session info channel as embed
    info_channel = guild.get_channel(CHANNELS["SESSION_INFO"])
    if info_channel:
        embed = discord.Embed(title="Session Info", description=f"```json\n{json.dumps(session_info, indent=2)}```", color=get_color())
        try:
            await info_channel.send(embed=embed)
        except:
            pass

# Session vote reaction handler
@bot.event
async def on_raw_reaction_add(payload):
    """Handle vote reactions"""
    if payload.message_id != session_data.get("vote_message_id"):
        return
    
    if str(payload.emoji) != VOTE_EMOJI:
        return
    
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    
    channel = guild.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    
    # Count votes (excluding bot)
    vote_count = 0
    for reaction in message.reactions:
        if str(reaction.emoji) == VOTE_EMOJI:
            async for user in reaction.users():
                if not user.bot:
                    vote_count += 1
            break
    
    threshold = session_data.get("vote_threshold", 0)
    
    if vote_count >= threshold:
        # Remove vote reactions
        for reaction in message.reactions:
            if str(reaction.emoji) == VOTE_EMOJI:
                await reaction.clear()
                break
        
        # Start the session
        starter = guild.get_member(payload.user_id)
        if starter:
            await start_session(starter, guild)
        
        # Notify in staff chat
        staff_channel = guild.get_channel(CHANNELS["STAFF_CHAT"])
        if staff_channel:
            session_ping = guild.get_role(CHANNELS["SESSION_PING"])
            await staff_channel.send(f"{starter.mention if starter else ''}: The Session Vote has received `{VOTE_EMOJI}/{threshold}. Would you like to begin the session?")

@bot.event
async def on_raw_reaction_remove(payload):
    """Handle vote reaction removal"""
    if payload.message_id != session_data.get("vote_message_id"):
        return
    
    if str(payload.emoji) != VOTE_EMOJI:
        return
    
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    
    channel = guild.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    
    # Re-add the reaction if votes dropped
    vote_count = 0
    for reaction in message.reactions:
        if str(reaction.emoji) == VOTE_EMOJI:
            async for user in reaction.users():
                if not user.bot:
                    vote_count += 1
            break
    
    if vote_count == 0:
        await message.add_reaction(VOTE_EMOJI)

# Background task for session reminders
@tasks.loop(minutes=60)
async def session_reminder_task():
    """Check and send session reminders"""
    if not session_data["active"] or not session_data["started_at"]:
        return
    
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    
    started_by_id = session_data.get("started_by")
    if not started_by_id:
        return
    
    elapsed = datetime.now() - session_data["started_at"]
    
    # After 1 hour, ask starter if session is still active
    if elapsed >= timedelta(hours=1) and elapsed < timedelta(hours=2):
        if not session_data.get("last_reminder") or (datetime.now() - session_data["last_reminder"]) >= timedelta(hours=1):
            starter = guild.get_member(started_by_id)
            if starter:
                embed = discord.Embed(color=get_color())
                embed.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&")
                
                embed2 = discord.Embed(
                    title="<:Offical_server:1475860128686411837> | Session Management",
                    description="As the session was started by you approximately an hour ago, please answer this question:\n> Is it currently still active?",
                    color=get_color()
                )
                embed2.set_image(url="https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&")
                
                view = SessionActiveView()
                try:
                    await starter.send(embeds=[embed, embed2], view=view)
                    session_data["last_reminder"] = datetime.now()
                except:
                    pass
    
    # After 2 hours, auto shutdown
    if elapsed >= timedelta(hours=2):
        exec_role = guild.get_role(ROLES["EXECUTIVE_COUNCIL"])
        management_role = guild.get_role(ROLES["MANAGEMENT"])
        
        # DM exec/management
        for member in guild.members:
            if exec_role in member.roles or management_role in member.roles:
                try:
                    embed = discord.Embed(
                        title="Session Auto-Shutdown Warning",
                        description="The session has been inactive for 2 hours. It will be auto-shutdown unless responded.",
                        color=get_color()
                    )
                    await member.send(embed=embed)
                except:
                    pass
        
        # Auto shutdown
        await shutdown_session(guild.me, guild)

class SessionActiveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
        self.add_item(discord.ui.Button(label="Yes", style=discord.ButtonStyle.green, custom_id="session_yes"))
        self.add_item(discord.ui.Button(label="No", style=discord.ButtonStyle.red, custom_id="session_no"))
    
    async def interaction_check(self, interaction: discord.Interaction):
        return True

@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle button interactions"""
    if interaction.data.get("custom_id") == "session_yes":
        await interaction.response.send_message("Thank you for confirming! The session remains active.", ephemeral=True)
    
    elif interaction.data.get("custom_id") == "session_no":
        guild = interaction.guild
        if guild:
            await shutdown_session(interaction.user, guild)
        await interaction.response.send_message("Session has been shutdown.", ephemeral=True)

# Regular commands (for prefix compatibility)
@bot.command(name="afk")
async def prefix_afk(ctx, *, message="AFK"):
    """Set AFK status via prefix"""
    await ctx.invoke(afk_command, message=message)

@bot.command(name="dmuser")
async def prefix_dmuser(ctx, user: discord.User, *, message):
    """DM a user via prefix"""
    await ctx.invoke(dmuser_command, user=user, message=message)

@bot.command(name="dmrole")
async def prefix_dmrole(ctx, role: discord.Role, *, message):
    """DM a role via prefix"""
    await ctx.invoke(dmrole_command, role=role, message=message)

@bot.command(name="warn")
async def prefix_warn(ctx, member: discord.Member, *, reason):
    """Warn a member via prefix"""
    await ctx.invoke(warn_command, member=member, reason=reason)

@bot.command(name="kick")
async def prefix_kick(ctx, member: discord.Member, *, reason):
    """Kick a member via prefix"""
    await ctx.invoke(kick_command, member=member, reason=reason)

@bot.command(name="ban")
async def prefix_ban(ctx, member: discord.Member, *, reason):
    """Ban a member via prefix"""
    await ctx.invoke(ban_command, member=member, reason=reason)

@bot.command(name="timeout")
async def prefix_timeout(ctx, member: discord.Member, duration: int, *, reason):
    """Timeout a member via prefix"""
    await ctx.invoke(timeout_command, member=member, duration=duration, reason=reason)

@bot.command(name="sessions")
async def prefix_sessions(ctx):
    """Session management via prefix"""
    await ctx.invoke(sessions_command)

# Run the bot
if __name__ == "__main__":
    # Keep Flask running
    keep_alive()
    
    # Get token from environment
    token = os.environ.get("DISCORD_TOKEN", "")
    if not token:
        logger.warning("No Discord token found. Please set DISCORD_TOKEN environment variable.")
        logger.info("Bot will start but won't connect without a valid token.")
    
    if token:
        bot.run(token)
    else:
        # Keep Flask running anyway
        while True:
            asyncio.sleep(1)

