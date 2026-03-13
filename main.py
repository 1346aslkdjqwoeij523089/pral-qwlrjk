import os
import json
import asyncio
import time
from datetime import datetime
from flask import Flask
import nextcord
from nextcord.ext import commands, tasks
from nextcord import app_commands
from nextcord.ui import View, Button, Select, Modal, TextInput

TOKEN = os.getenv('TOKEN')
GUILD_ID = 1464682632204779602
COLOR = 0x004bae
PREFIX = '<'

# Constants
guild_id = int(GUILD_ID)
channels = {
    'welcome': 1464682633371062293,
    'voice_membercount': 1471478613038600328,
    'session_status': 1480013219199451308,
    'session_ch': 1464682633559801939,
    'staff_chat': 1464682633853407327,
    'session_ping': 1465771610312278180,
    'logs': 1480024519677706382,
    'pinned_msg': 1480023088799416451  # ID for except in deletes
}
roles = {
    'foundation': 1464682632754233539,
    'exec': 1466490625259212821,
    'mgmt': 1464682632754233535,
    'dev': 1479003906531917886,
    'staff_high': 1464682632729071818,  # etc.
}
session_emoji = {'active': '🟢', 'inactive': '🔴'}
dev_role = roles['dev']
mgmt_roles = [roles['mgmt'], roles['exec']]  # + 

DATA_DIR = 'data'
LOGS_FILE = 'logs/actions.txt'
AFK_FILE = f'{DATA_DIR}/afk.json'
SESSION_FILE = f'{DATA_DIR}/sessions.json'

intents = nextcord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return 'Bot alive!'

async def load_json(file):
    def _load():
        if not os.path.exists(file) or os.path.getsize(file) == 0:
            return {}
        with open(file, 'r') as f:
            return json.load(f)
    return await asyncio.to_thread(_load)

async def save_json(file, data):
    def _save():
        os.makedirs(os.path.dirname(file) or '.', exist_ok=True)
        with open(file, 'w') as f:
            json.dump(data, f)
    await asyncio.to_thread(_save)

async def log_action(action, user_id):
    def _log():
        os.makedirs('logs', exist_ok=True)
        with open(LOGS_FILE, 'a') as f:
            f.write(f'{datetime.now()}: user {user_id} {action}\n')
    await asyncio.to_thread(_log)

class SessionView(View):
    def __init__(self):
        super().__init__(timeout=300)

    async def check_status(self):
        guild = bot.get_guild(guild_id)
        if not guild:
            return False
        ch = guild.get_channel(channels['session_status'])
        if not ch:
            return False
        return ch.name.endswith(session_emoji['active'])

    @nextcord.ui.button(label='Boost', style=nextcord.ButtonStyle.primary, emoji='📈')
    async def boost(self, btn: Button, inter: nextcord.Interaction):
        if not await self.check_status():
            return await inter.response.send_message('Session inactive.', ephemeral=True)
        await self.action_embed('low', inter.user)
        await inter.response.send_message('Boost sent.', ephemeral=True)

    @nextcord.ui.button(label='Shutdown', style=nextcord.ButtonStyle.danger)
    async def shutdown(self, btn: Button, inter: nextcord.Interaction):
        data = await load_session()
        if time.time() < data.get('cooldown_until', 0):
            mins = int((data['cooldown_until'] - time.time()) / 60)
            return await inter.response.send_message(f'15min cooldown. {mins}min left.', ephemeral=True)
        await self.action_embed('shutdown', inter.user)
        await inter.response.send_message('Shutdown sent.', ephemeral=True)

    @nextcord.ui.button(label='Full', style=nextcord.ButtonStyle.success)
    async def full(self, btn: Button, inter: nextcord.Interaction):
        if not await self.check_status():
            return await inter.response.send_message('Session inactive.', ephemeral=True)
        await self.action_embed('full', inter.user)
        await inter.response.send_message('Full sent.', ephemeral=True)

    @nextcord.ui.button(label='Vote', style=nextcord.ButtonStyle.secondary)
    async def vote(self, btn: Button, inter: nextcord.Interaction):
        modal = VoteModal()
        await inter.response.send_modal(modal)

    @nextcord.ui.button(label='Start', style=nextcord.ButtonStyle.green)
    async def start(self, btn: Button, inter: nextcord.Interaction):
        data = await load_session()
        if data.get('active', False):
            return await inter.response.send_message('Session active.', ephemeral=True)
        await session_start(inter.user)
        await inter.response.send_message('Session started.', ephemeral=True)

    async def action_embed(self, action, user):
        guild = bot.get_guild(guild_id)
        ch = guild.get_channel(channels['session_ch'])
        await delete_except_pinned(ch)
        if action == 'shutdown':
            embed = nextcord.Embed(color=COLOR, description=f'A session has been shut down by **{user.display_name}**. Thank you!')
            embed.set_image(url='https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png')
            await ch.send(embed=embed)
            await channel_name(channels['session_status'], session_emoji['inactive'])
            await save_session({'active': False})
        elif action == 'low':
            embed = nextcord.Embed(color=COLOR, description=f'**Low player count** - Boost requested by **{user.display_name}**.')
            await ch.send(embed=embed)
        elif action == 'full':
            embed = nextcord.Embed(color=COLOR, description=f'Session is **full**. Alert by **{user.display_name}**.')
            await ch.send(embed=embed)
        await log_action(f'session_{action}', user.id)

class VoteModal(Modal):
    def __init__(self):
        super().__init__(title='Session Vote Threshold')
        self.threshold = TextInput(label='Votes needed', placeholder='e.g. 10')

    async def callback(self, inter: nextcord.Interaction):
        try:
            thresh = int(self.threshold.value)
        except:
            return await inter.response.send_message('Invalid number.', ephemeral=True)
        await session_vote(inter.user, thresh)
        await inter.response.send_message('Vote started.', ephemeral=True)

async def load_afk():
    return await load_json(AFK_FILE) or {}

async def save_afk(data):
    await save_json(AFK_FILE, data)

async def load_session():
    return await load_json(SESSION_FILE) or {'active': False, 'votes': 0}

async def save_session(data):
    await save_json(SESSION_FILE, data)

async def channel_name(ch_id, name_suffix):
    guild = bot.get_guild(guild_id)
    ch = guild.get_channel(ch_id)
    if ch:
        await ch.edit(name=f"Sessions: {name_suffix}")

async def delete_except_pinned(ch):
    msgs = [msg async for msg in ch.history(limit=50)]
    to_del = [msg for msg in msgs if msg.id != channels['pinned_msg']]
    if to_del:
        await ch.delete_messages(to_del)

async def session_start(user):
    await channel_name(channels['session_status'], session_emoji['active'])
    data = {'active': True, 'starter': user.id, 'start_time': time.time(), 'cooldown_until': time.time() + 900, 'votes': 0}
    await save_session(data)
    guild = bot.get_guild(guild_id)
    ch = guild.get_channel(channels['session_ch'])
    await delete_except_pinned(ch)
    embed1 = nextcord.Embed(color=COLOR)
    embed1.set_image(url='https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png')
    embed2 = nextcord.Embed(title='__ <:Offical_server:1475860128686411837> | 𝓛𝓐𝓡𝓟 Session__ ', color=COLOR, description=f'<@{channels["session_ping"]}>\\nAfter votes, session begun. In-Game Code: L')
    embed2.set_image(url='https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png')
    await ch.send(embeds=[embed1, embed2])
    await log_action('session_start', user.id)
    asyncio.create_task(session_dm_loop(user.id))

async def session_vote(user, thresh):
    data = await load_session()
    data.setdefault('votes', 0)
    data['votes'] += 1
    await save_session(data)
    guild = bot.get_guild(guild_id)
    ch = guild.get_channel(channels['session_ch'])
    embed = nextcord.Embed(color=COLOR, description=f'Vote #{data["votes"]} / {thresh} by **{user.display_name}**.')
    await ch.send(embed=embed)
    if data['votes'] >= thresh:
        await session_start(user)
    await log_action('session_vote', user.id)

async def session_shutdown():
    await channel_name(channels['session_status'], session_emoji['inactive'])
    await save_session({'active': False})
    guild = bot.get_guild(guild_id)
    ch = guild.get_channel(channels['session_ch'])
    embed = nextcord.Embed(color=COLOR, description='Session shut down.')
    await ch.send(embed=embed)
    await log_action('session_shutdown', 0)

async def session_dm_loop(starter_id):
    await asyncio.sleep(3600)
    user = bot.get_user(starter_id)
    if user:
        embed = nextcord.Embed(title='Session Check', description='Is it still active?', color=COLOR)
        await user.send(embed=embed)

def has_perm(member, role_list):
    return any(role.id in role_list for role in member.roles)

@tasks.loop(minutes=15)
async def membercount_loop():
    guild = bot.get_guild(guild_id)
    if guild:
        humans = len([m for m in guild.members if not m.bot])
        ch = guild.get_channel(channels['voice_membercount'])
        if ch and isinstance(ch, nextcord.VoiceChannel):
            await ch.edit(name=f'Members: {humans}')

@bot.event
async def on_ready():
    print(f'{bot.user} logged in.')
    guild = nextcord.Object(id=guild_id)
    bot.tree.sync(guild=guild)
    membercount_loop.start()
    # session_check.start()  # Stubbed

@bot.event
async def on_member_join(member):
    ch = bot.get_channel(channels['welcome'])
    if ch:
        embed = nextcord.Embed(color=COLOR)
        embed.set_image(url='https://cdn.discordapp.com/attachments/1479259996846948483/1479260063192584273/welcomelarp.png')
        await ch.send(f'{member.mention}', embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    afk_data = await load_afk()
    for mention in message.mentions:
        if str(mention.id) in afk_data:
            reason = afk_data[str(mention.id)]['reason']
            embed = nextcord.Embed(title=f'{mention.display_name} is AFK', description=reason, color=COLOR)
            await message.reply(embed=embed)
            afk_data[str(mention.id)]['mentions'].append({'from': message.author.id, 'msg': message.id})
            await save_afk(afk_data)
    if str(message.author.id) in afk_data:
        del afk_data[str(message.author.id)]
        await save_afk(afk_data)
        guild = message.guild
        old_nick = afk_data.get('old_nick', message.author.display_name)
        await guild.edit_member(message.author.id, nick=old_nick)
    if message.content.startswith(PREFIX + 'sessions') and any(x in message.content.lower() for x in ['p', 'pr', 'pri', 'priv', 'priva', 'privat']):
        if not has_perm(message.author, mgmt_roles):
            await message.delete()
            embed = nextcord.Embed(description='Only Management+ permitted.', color=0xff0000)
            tmp = await message.channel.send(embed=embed)
            await asyncio.sleep(5)
            await tmp.delete()
            return
    await bot.process_commands(message)

@bot.hybrid_command(name='dmuser')
async def dm_user(ctx, user: str, *, msg: str):
    if not has_perm(ctx.author, [roles['exec'], dev_role]):
        return await ctx.send('No perm.', ephemeral=True if ctx.interaction else False)
    try:
        uid = int(user.replace('<@', '').replace('>', ''))
        user_obj = await bot.fetch_user(uid)
        now = datetime.now().strftime('%I:%M%p')
        embed = nextcord.Embed(title='𝓛𝓐𝓡𝓟 - New DM', color=COLOR)
        embed.add_field(name='From', value=ctx.author.display_name, inline=False)
        embed.add_field(name=msg, value='', inline=False)
        embed.set_footer(text=f'Sent at {now}')
        await user_obj.send(embed=embed)
        await ctx.send('DM sent.', ephemeral=True if ctx.interaction else False)
        await log_action('dmuser', ctx.author.id)
    except:
        await ctx.send('Invalid user.', ephemeral=True if ctx.interaction else False)

@bot.hybrid_command(name='afk')
async def afk(ctx, *, reason: str = 'AFK'):
    old_nick = ctx.author.display_name
    new_nick = f'AFK • {old_nick}'
    await ctx.guild.edit_member(ctx.author.id, nick=new_nick)
    afk_data = await load_afk()
    afk_data[str(ctx.author.id)] = {'reason': reason, 'mentions': [], 'old_nick': old_nick}
    await save_afk(afk_data)
    embed = nextcord.Embed(title=f'{ctx.author.display_name}', description=f'You are now AFK for {reason}.', color=COLOR)
    await ctx.send(embed=embed)
    await log_action('afk_set', ctx.author.id)

@bot.tree.command(name='sessions', guild=nextcord.Object(id=guild_id))
async def sessions_slash(inter: nextcord.Interaction):
    if not has_perm(inter.user, mgmt_roles):
        embed = nextcord.Embed(description='Only Management+.', color=0xff0000)
        return await inter.response.send_message(embed=embed, ephemeral=True)
    is_active = await SessionView().check_status()
    embed1 = nextcord.Embed(color=COLOR).set_image(url='https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png')
    desc = f'Welcome, {inter.user.mention}.\\n'
    status_ch = bot.get_guild(guild_id).get_channel(channels['session_status'])
    status_text = '**currently active**' if status_ch and status_ch.name.endswith('🟢') else '**currently inactive**'
    desc += f'The Session is {status_text}.\\nClick below.'
    if is_active:
        desc += '- **Boost**\\n- **Shutdown**\\n- **Full** alert.'
    else:
        desc += '- Initiate **Vote**.\\n- **Start** new.'
    embed2 = nextcord.Embed(title='Session Management', description=desc, color=COLOR)
    embed3 = nextcord.Embed(color=COLOR).set_image(url='https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png')
    view = SessionView()
    await inter.response.send_message(embeds=[embed1, embed2, embed3], view=view, ephemeral=True)

async def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    try:
        await bot.load_extension('jishaku')
    except:
        pass  # Optional
    async with flask_app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080))) as _:
        await bot.start(TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
