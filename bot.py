#! /usr/bin/python
import traceback
try:
    import discord
    from discord.ext import commands, tasks
    import os
    from dotenv import load_dotenv
    import aiohttp
    import json
except Exception as e:
    print("--- Environment error! Details are listed below.")
    traceback.print_exc()
    exit(2)


load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.reactions = True
intents.message_content = False
bot = commands.Bot(command_prefix='!', intents=intents)

# Configuration
CHANNEL_ID = 1442510096658595870
STATUS_CHANNEL_ID = 1442512052101840999
ROLE_ID = 1442510446656491643
MESSAGE_TEXT = "React with :money_mouth: to get the notification role!"
SLACK_CHECK_URL = "https://isslackdown.davidwhy.me/"

# State tracking
slack_is_up = False
already_pinged = False
monitoring_enabled = False

@bot.event
async def on_ready():
    global monitoring_enabled
    print(f'{bot.user} has connected to Discord!')
    
    # Check if "START" message exists in status channel
    status_channel = bot.get_channel(STATUS_CHANNEL_ID)
    if status_channel:
        async for message in status_channel.history(limit=100):
            if "START" in message.content:
                monitoring_enabled = True
                print("Found 'START' message - monitoring enabled")
                break
    
    if not monitoring_enabled:
        print("'START' message not found - monitoring disabled")
    
    # Run check immediately if monitoring is enabled
    if monitoring_enabled:
        await check_slack_status()
    
    # Start the background task (if not already running)
    if not check_slack_status.is_running():
        check_slack_status.start()
    
    # Send the message to the channel
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        # Check if message already exists
        async for message in channel.history(limit=100):
            if message.author == bot.user and MESSAGE_TEXT in message.content:
                print(f'Message already exists: {message.id}')
                return
        
        # Send new message
        msg = await channel.send(MESSAGE_TEXT)
        print(f'Sent message: {msg.id}')

@bot.event
async def on_raw_reaction_add(payload):
    print(f"Reaction detected: {payload.emoji.name} in channel {payload.channel_id}")
    
    # Check if reaction is in the correct channel
    if payload.channel_id != CHANNEL_ID:
        print(f"Wrong channel: {payload.channel_id} != {CHANNEL_ID}")
        return
    
    # Check if reaction is money_mouth emoji (🤑)
    if str(payload.emoji) != '🤑':
        print(f"Wrong emoji: {payload.emoji} != 🤑")
        return
    
    print("Correct emoji in correct channel")
    
    # Get the guild and member
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        print("Guild not found")
        return
    
    try:
        member = await guild.fetch_member(payload.user_id)
    except:
        member = guild.get_member(payload.user_id)
    
    if not member or member.bot:
        print(f"Member not found or is bot: {member}")
        return
    
    # Add the role
    role = guild.get_role(ROLE_ID)
    if role:
        try:
            await member.add_roles(role)
            print(f'Added role to {member}: {role.name}')
        except Exception as e:
            print(f"Error adding role: {e}")
    else:
        print(f"Role {ROLE_ID} not found")
        print(f"Available roles: {[r.name for r in guild.roles]}")

@bot.event
async def on_raw_reaction_remove(payload):
    # Check if reaction is in the correct channel
    if payload.channel_id != CHANNEL_ID:
        return
    
    # Check if reaction is money_mouth emoji (🤑)
    if str(payload.emoji) != '🤑':
        return
    
    # Get the guild and member
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    
    try:
        member = await guild.fetch_member(payload.user_id)
    except:
        member = guild.get_member(payload.user_id)
    
    if not member or member.bot:
        return
    
    # Remove the role
    role = guild.get_role(ROLE_ID)
    if role:
        await member.remove_roles(role)
        print(f'Removed role from {member}: {role.name}')

@tasks.loop(minutes=5)
async def check_slack_status():
    global slack_is_up, already_pinged, monitoring_enabled
    
    if not monitoring_enabled:
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(SLACK_CHECK_URL, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                
                # Check if Slack is up
                if data.get("message") == "Slack is now up!":
                    # Slack is up
                    if not slack_is_up:
                        # Slack just came back up
                        slack_is_up = True
                        already_pinged = False
                    
                    # If we haven't pinged yet, ping now
                    if not already_pinged:
                        status_channel = bot.get_channel(STATUS_CHANNEL_ID)
                        if status_channel:
                            role = status_channel.guild.get_role(ROLE_ID)
                            if role:
                                await status_channel.send(f"{role.mention} SLACK IS BACK!")
                                already_pinged = True
                                print("Pinged role - Slack is back!")
                else:
                    # Slack is still down
                    if slack_is_up:
                        # Slack just went down
                        slack_is_up = False
                        already_pinged = False
                    
                    # Send down message
                    channel = bot.get_channel(CHANNEL_ID)
                    if channel:
                        await channel.send("Slack is still down :(")
                    
                    status_channel = bot.get_channel(STATUS_CHANNEL_ID)
                    if status_channel:
                        await status_channel.send("🔴 Slack is still down :(")
                    
                    print("Slack is still down")
    
    except Exception as e:
        print(f"Error checking Slack status: {e}")
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("Slack is still down :(")

# Run the bot
try:
    with open("/run/secrets/DISCORD_TOKEN", "r") as docker_secret:
        TOKEN = docker_secret.read().strip()
except Exception as e:
    print(e)
    print(os.listdir("/run/secrets"))
    TOKEN = os.getenv('DISCORD_TOKEN')
print(f"Token loaded: {TOKEN[:10] if TOKEN else 'None'}...")
if not TOKEN:
    print("Error: No token found")
    exit(126)
else:
    print("Token found, attempting connection...")
    bot.run(TOKEN)
