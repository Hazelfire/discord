import discord
import asyncio
from datetime import datetime, timedelta

AUTH_TOKEN = ""

client = discord.Client()

@client.event
async def on_ready():
    for server in client.servers:
        me = server.get_member(client.user.id)
        for channel in server.channels:
            if channel.permissions_for(me).read_messages:
                logs = client.logs_from(channel, after=(datetime.now() - timedelta(days=1)))
                async for log in logs:
                    print(server.name + " - " + channel.name + " - " + log.author.nick + (" (mentioned)" if me.mentioned_in(log) else ""))

    await client.close()
    



client.run(AUTH_TOKEN, bot=False)
