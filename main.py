import os
import re
import asyncio
from flask import Flask, render_template
from threading import Thread
import nextcord
from nextcord.ext import commands
from nextcord.ext import tasks
from nextcord import slash_command, SlashOption

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
GUILD_ID = 1464682632204779602  # Server ID to count members from

# Role IDs for AFK command access
AFK_ALLOWED_ROLE_IDS = [
    1464682632661958858,
    1464682632729071818,
    1464682632754233535,
    1466490625259212821,
    1465966607669919795,
    1464682632754233539
]

# AFK storage: {user_id: {"reason": str, "nickname": str, "start_time": timestamp, "mentions": []}}
afk_data = {}

# Footer image URL
FOOTER_IMAGE_URL = "https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ab6798&is=69aa1618&hm=1d2252bf2f7eb6cfb39919584fada1db4f56e73a4721967df64e6dd509b38224&"

def has_say_permission(member):
    """Check if member has any of the allowed roles for say command"""
    if not member:
        return False
    for role in member.roles:
        if role.id in AFK_ALLOWED_ROLE_IDS:
            return True
    return False

def has_afk_permission(member):
    """Check if member has any of the allowed roles for AFK command"""
    if not member:
        return False
    for role in member.roles:
        if role.id in AFK_ALLOWED_ROLE_IDS:
            return True
    return False

def create_afk_permission_denied_embed():
    """Create embed for when user doesn't have permission for AFK"""
    embed1 = nextcord.Embed(
        title="<@&1478894384597700669> | 𝓛𝓐𝓡𝓟 Services",
        description="You must be Internal Affairs+ to use the functionality of AFK.",
        color=0x004bae
    )
    embed2 = nextcord.Embed()
    embed2.color = 0x004bae
    embed2.set_image(url=FOOTER_IMAGE_URL)
    return [embed1, embed2]

def format_afk_time(seconds):
    """Format seconds into 'X hours ago' or 'X minutes ago' etc."""
    if seconds < 60:
        return f"{seconds} seconds ago"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        return f"{days} day{'s' if days != 1 else ''} {hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''} ago"

def format_duration(seconds):
    """Format seconds into 'X hours, Y minutes, and Z seconds'"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs > 0 or not parts:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")
    
    if len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    else:
        return f"{parts[0]}, {parts[1]}, and {parts[2]}"

def parse_time(time_str):
    """Parse time string like 15s, 1d, 15min, 1hr etc. Returns seconds or None"""
    if not time_str:
        return None
    
    time_str = time_str.lower().strip()
    
    # Patterns for different time formats
    patterns = [
        (r'^(\d+)s$', 1),           # 15s
        (r'^(\d+)sec$', 1),         # 15sec
        (r'^(\d+)m$', 60),          # 15m
        (r'^(\d+)min$', 60),        # 15min
        (r'^(\d+)h$', 3600),       # 15h
        (r'^(\d+)hr$', 3600),      # 15hr
        (r'^(\d+)d$', 86400),      # 1d
        (r'^(\d+)day$', 86400),    # 1day
    ]
    
    for pattern, multiplier in patterns:
        match = re.match(pattern, time_str)
        if match:
            return int(match.group(1)) * multiplier
    
    return None

def create_permission_denied_embed():
    """Create embed for when user doesn't have permission"""
    embed1 = nextcord.Embed(
        title="<@&1478894384597700669> | 𝓛𝓐𝓡𝓟 Services",
        description="You must be Chief of Staff+ in Los Angeles Roleplay in order to use the bot functionality of say",
        color=0x004bae
    )
    embed2 = nextcord.Embed()
    embed2.color = 0x004bae
    embed2.set_image(url=FOOTER_IMAGE_URL)
    return [embed1, embed2]

# Set bot activity and name
@bot.event
async def on_ready():
    await bot.change_presence(activity=nextcord.Activity(type=nextcord.ActivityType.playing, name="Los Angeles Roleplay"))
    print(f'Bot is logged in as {bot.user.name}')
    # Start the member count updater task
    update_member_count.start()
    # Sync slash commands
    bot.add_view(SlashCommandSyncView())
    # Sync application commands with Discord
    await bot.sync_application_commands()
    print("Slash commands synced!")

# Task to update member count every 10 minutes
@tasks.loop(minutes=10)
async def update_member_count():
    try:
        # Get the specific guild by ID
        guild = bot.get_guild(GUILD_ID)
        if guild:
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
        
        # Create Image Embed 1 - show as actual image, not hyperlink
        embed1 = nextcord.Embed()
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
    
    # Check for <say command
    if message.content.startswith("<say "):
        # Check permission
        if not has_say_permission(message.author):
            reply_msg = await message.reply(embeds=create_permission_denied_embed())
            await message.delete()
            await reply_msg.delete(delay=15)
            return
        
        # Extract the text to say (everything after <say )
        say_text = message.content[5:].strip()  # Remove "<say " prefix
        
        if not say_text:
            return
        
        # Delete user's message
        await message.delete()
        
        # Send the message in the same channel
        bot_message = await message.channel.send(say_text)
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
            
            # Reply to the user and delete after 15 seconds
            reply_message = await message.reply(embeds=[embed1, embed2])
            await reply_message.delete(delay=15)
            
        except Exception as e:
            print(f"Error responding to bot mention: {e}")
    
    # Check for mentions of AFK users
    for mention in message.mentions:
        if mention.id in afk_data:
            afk_info = afk_data[mention.id]
            afk_reason = afk_info["reason"]
            afk_start_time = afk_info["start_time"]
            import time
            afk_time_ago = format_afk_time(int(time.time() - afk_start_time))
            
            # Get the AFK user's current nickname
            afk_nickname = mention.nick if mention.nick else mention.name
            
            # Send the AFK notification in the channel (no reply, no auto-delete)
            afk_message = f"`{afk_nickname}` has been AFK {afk_reason} - {afk_time_ago}"
            await message.channel.send(afk_message)
            
            # Record the mention
            mentioner_nickname = message.author.nick if message.author.nick else message.author.name
            afk_info["mentions"].append({
                "user_id": message.author.id,
                "name": mentioner_nickname,
                "timestamp": time.time()
            })
    
    # Check if the author was AFK and is now returning
    if message.author.id in afk_data:
        # Create a fake ctx-like object for handling AFK return
        class FakeCtx:
            def __init__(self, message):
                self.author = message.author
                self.guild = message.guild
                self.channel = message.channel
                self.send = message.channel.send
                self.reply = message.reply
        
        fake_ctx = FakeCtx(message)
        await handle_afk_return(fake_ctx, message.author)
    
    # Process commands (if any)
    await bot.process_commands(message)

# Slash command view for syncing
class SlashCommandSyncView(nextcord.ui.View):
    def __init__(self):
        super().__init__()

# /sync slash command - Manually sync all slash commands
@bot.slash_command(description="Sync all slash commands with Discord", guild_ids=[GUILD_ID])
async def sync(interaction: nextcord.Interaction):
    """Sync all slash commands with Discord"""
    try:
        # Check if user has permission (must be bot developer or admin)
        if interaction.user.id != DEVELOPER_USER_ID:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        await bot.sync_application_commands()
        await interaction.response.send_message("✅ All slash commands have been synced!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error syncing commands: {e}", ephemeral=True)

# /say slash command
@bot.slash_command(description="Send a message to a specified channel with optional delay", guild_ids=[GUILD_ID])
async def say(
    interaction: nextcord.Interaction,
    text: str = SlashOption(description="The text to send", required=True),
    channel: nextcord.TextChannel = SlashOption(
        description="The channel to send to (defaults to current channel)",
        required=False
    ),
    time: str = SlashOption(
        description="Delay before sending (e.g., 15s, 1d, 15min, 1hr)",
        required=False
    )
):
    # Check permission
    if not has_say_permission(interaction.user):
        await interaction.response.send_message(embeds=create_permission_denied_embed(), ephemeral=True)
        return
    
    # Use current channel if none specified
    target_channel = channel if channel else interaction.channel
    
    # Parse time delay
    delay_seconds = parse_time(time)
    
    if delay_seconds:
        # Send with delay
        await interaction.response.send_message(f"Message will be sent in {target_channel.mention} in {time}", ephemeral=True)
        
        async def delayed_send():
            await target_channel.send(text)
        
        # Schedule the delayed message
        bot.loop.call_later(delay_seconds, lambda: asyncio.ensure_future(delayed_send()))
    else:
        # Send immediately
        await target_channel.send(text)
        await interaction.response.send_message(f"Message sent to {target_channel.mention}", ephemeral=True)

# Example command
@bot.command()
async def ping(ctx):
    await ctx.send('Pong! Los Angeles Roleplay is online!')

# <afk prefix command
@bot.command(name="afk")
async def afk_prefix(ctx, *, args=None):
    """Set AFK status with optional reason and time"""
    # Get member from guild
    member = ctx.author
    
    # Check permission
    if not has_afk_permission(member):
        reply_msg = await ctx.reply(embeds=create_afk_permission_denied_embed())
        await reply_msg.delete(delay=15)
        return
    
    # Check if already AFK - if so, remove AFK
    if member.id in afk_data:
        # User is returning from AFK
        await handle_afk_return(ctx, member)
        return
    
    # Parse arguments
    reason = "AFK"
    time_str = None
    
    if args:
        # Try to find time pattern at the end
        time_patterns = [
            r'^(.+?)\s+(\d+d)$',
            r'^(.+?)\s+(\d+day)$',
            r'^(.+?)\s+(\d+h)$',
            r'^(.+?)\s+(\d+hr)$',
            r'^(.+?)\s+(\d+min)$',
            r'^(.+?)\s+(\d+m)$',
            r'^(.+?)\s+(\d+s)$',
            r'^(.+?)\s+(\d+sec)$',
        ]
        
        matched = False
        for pattern in time_patterns:
            match = re.match(pattern, args, re.IGNORECASE)
            if match:
                reason = match.group(1).strip() if match.group(1).strip() else "AFK"
                time_str = match.group(2)
                matched = True
                break
        
        if not matched:
            reason = args.strip() if args.strip() else "AFK"
    
    # Set AFK
    await set_afk_status(ctx, member, reason, time_str)

async def set_afk_status(ctx, member, reason, time_str=None):
    """Set the AFK status for a member"""
    import time
    
    guild = ctx.guild
    current_nickname = member.nick if member.nick else member.name
    
    # Store AFK data
    afk_data[member.id] = {
        "reason": reason,
        "nickname": current_nickname,
        "start_time": time.time(),
        "mentions": [],
        "guild_id": guild.id
    }
    
    # Try to update nickname with AFK prefix
    try:
        afk_nickname = f"AFK・{current_nickname}"
        if len(afk_nickname) > 32:
            # Nickname too long, send DM instead
            await member.send("Unable to update your nickname with AFK status due to the length of your nickname being too long. You are still AFK on status.")
        else:
            await member.edit(nick=afk_nickname)
    except Exception as e:
        print(f"Error updating nickname: {e}")
        try:
            await member.send("Unable to update your nickname with AFK status. You are still AFK on status.")
        except:
            pass
    
    # Create the response embed
    embed1 = nextcord.Embed(
        color=0x004bae
    )
    embed1.description = f"**{member.nick if member.nick else member.name}**\n" \
        f"> You are now away from your keyboard [AFK] for {reason}.\n" \
        f"> Members will be notified about your status.\n" \
        f"> When you are back to your keyboard, you will be shown all the people who mentioned you while you were AFK."
    
    embed2 = nextcord.Embed()
    embed2.color = 0x004bae
    embed2.set_image(url=FOOTER_IMAGE_URL)
    
    await ctx.send(embeds=[embed1, embed2])
    
    # If time specified, schedule auto-return
    if time_str:
        delay_seconds = parse_time(time_str)
        if delay_seconds:
            async def auto_return():
                if member.id in afk_data:
                    try:
                        # Remove AFK
                        if member.nick and member.nick.startswith("AFK・"):
                            original_nickname = member.nick[4:]
                            if len(original_nickname) <= 32:
                                await member.edit(nick=original_nickname)
                    except:
                        pass
                    del afk_data[member.id]
            
            bot.loop.call_later(delay_seconds, lambda: asyncio.ensure_future(auto_return()))

async def handle_afk_return(ctx, member):
    """Handle when a user returns from AFK"""
    import time
    
    if member.id not in afk_data:
        return
    
    afk_info = afk_data[member.id]
    reason = afk_info["reason"]
    mentions = afk_info.get("mentions", [])
    start_time = afk_info["start_time"]
    
    # Calculate duration
    duration_seconds = int(time.time() - start_time)
    duration_str = format_duration(duration_seconds)
    
    # Get timestamp when they went AFK
    afk_time_str = format_afk_time(duration_seconds)
    
    # Restore nickname
    try:
        if member.nick and member.nick.startswith("AFK・"):
            original_nickname = member.nick[4:]
            if len(original_nickname) <= 32:
                await member.edit(nick=original_nickname)
    except Exception as e:
        print(f"Error restoring nickname: {e}")
    
    # Build embed description
    description = f"**{member.nick if member.nick else member.name}**\n" \
        f"> You are now back at your keyboard after {reason}.\n" \
        f"> You have been AFK for {duration_str}.\n"
    
    if mentions:
        for mention_info in mentions:
            mentioner_name = mention_info["name"]
            description += f"> `{mentioner_name}`\n> \"How are you doing?\"\n> {afk_time_str} at <t:{int(start_time)}:t>\n\n"
    else:
        description += f"> Here is the\n> No one has mentioned you while you were AFK."
    
    embed1 = nextcord.Embed(
        color=0x004bae
    )
    embed1.description = description
    
    embed2 = nextcord.Embed()
    embed2.color = 0x004bae
    embed2.set_image(url=FOOTER_IMAGE_URL)
    
    await ctx.reply(embeds=[embed1, embed2], content=member.mention)
    
    # Remove from AFK data
    del afk_data[member.id]

# /afk slash command
@bot.slash_command(description="Set your AFK status", guild_ids=[GUILD_ID])
async def afk(
    interaction: nextcord.Interaction,
    reason: str = SlashOption(description="Reason for being AFK", required=False),
    time: str = SlashOption(description="Time until auto-return (e.g., 15s, 1d, 15min, 1hr)", required=False)
):
    """Set AFK status with optional reason and time"""
    member = interaction.user
    
    # Check permission
    if not has_afk_permission(member):
        await interaction.response.send_message(embeds=create_afk_permission_denied_embed(), ephemeral=True)
        return
    
    # Check if already AFK - if so, remove AFK
    if member.id in afk_data:
        # User is returning from AFK - create a fake ctx-like object
        class FakeCtx:
            def __init__(self, interaction):
                self.author = interaction.user
                self.guild = interaction.guild
                self.channel = interaction.channel
                self.send = lambda **kwargs: interaction.followup.send(**kwargs)
                self.reply = lambda **kwargs: interaction.followup.send(**kwargs)
        
        fake_ctx = FakeCtx(interaction)
        await handle_afk_return(fake_ctx, member)
        return
    
    # Set AFK
    await set_afk_status_slash(interaction, member, reason, time)

async def set_afk_status_slash(interaction, member, reason, time_str=None):
    """Set the AFK status for a member (slash command version)"""
    import time
    
    guild = interaction.guild
    current_nickname = member.nick if member.nick else member.name
    
    # Store AFK data
    afk_data[member.id] = {
        "reason": reason if reason else "AFK",
        "nickname": current_nickname,
        "start_time": time.time(),
        "mentions": [],
        "guild_id": guild.id
    }
    
    # Try to update nickname with AFK prefix
    nickname_error = None
    try:
        afk_nickname = f"AFK・{current_nickname}"
        if len(afk_nickname) > 32:
            nickname_error = "Unable to update your nickname with AFK status due to the length of your nickname being too long. You are still AFK on status."
        else:
            await member.edit(nick=afk_nickname)
    except Exception as e:
        print(f"Error updating nickname: {e}")
        nickname_error = "Unable to update your nickname with AFK status. You are still AFK on status."
    
    # Create the response embed
    embed1 = nextcord.Embed(
        color=0x004bae
    )
    embed1.description = f"**{member.nick if member.nick else member.name}**\n" \
        f"> You are now away from your keyboard [AFK] for {reason if reason else 'AFK'}.\n" \
        f"> Members will be notified about your status.\n" \
        f"> When you are back to your keyboard, you will be shown all the people who mentioned you while you were AFK."
    
    embed2 = nextcord.Embed()
    embed2.color = 0x004bae
    embed2.set_image(url=FOOTER_IMAGE_URL)
    
    await interaction.response.send_message(embeds=[embed1, embed2])
    
    # Send DM if nickname error
    if nickname_error:
        try:
            await member.send(nickname_error)
        except:
            pass
    
    # If time specified, schedule auto-return
    if time_str:
        delay_seconds = parse_time(time_str)
        if delay_seconds:
            async def auto_return():
                if member.id in afk_data:
                    try:
                        # Remove AFK
                        if member.nick and member.nick.startswith("AFK・"):
                            original_nickname = member.nick[4:]
                            if len(original_nickname) <= 32:
                                await member.edit(nick=original_nickname)
                    except:
                        pass
                    del afk_data[member.id]
            
            bot.loop.call_later(delay_seconds, lambda: asyncio.ensure_future(auto_return()))

# Run the bot - use TOKEN environment variable (for Render.com deployment)
keep_alive()
bot.run(os.environ.get('TOKEN'))

