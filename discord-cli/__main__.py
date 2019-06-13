"""
File: __main__.py
Author: Sam Nolan
Email: sam.nolan@rmit.edu.au
Github: https://github.com/Hazelfire
Description: The entry point for my discord cli
"""

import asyncio
from datetime import datetime
import os
import sys
import json
import discord
from botsunlimited import bots

AUTH_TOKEN = os.environ["DISCORD_TOKEN"]

client = discord.Client()


class DiscordState:
    """ Holds the running state of the program, current channel, guild etc """
    channel = None
    guild = None

state = DiscordState()

def make_folder(folder):
    if not os.path.exists(folder):
        os.makedirs(folder)


discord_conf_dir = os.path.expanduser("~/.config/discord-cli")
make_folder(discord_conf_dir)
timestamp_file = discord_conf_dir + "/lastread"
aliases_file = discord_conf_dir + "/aliases"


def write_alias_file(new_aliases):
    with open(aliases_file, "w") as f:
        f.write(json.dumps(new_aliases))


if not os.path.exists(aliases_file):
    write_alias_file({"server": [], "channel": [], "user": [], "role": []})


def print_message(message):
    nick = (
        message.author.nick
        if hasattr(message.author, "nick") and message.author.nick
        else message.author.name
    )
    print(
            "{}: {}".format(
            nick,
            message.content,
        )
    )


async def print_channel(channel):
    lastread = datetime.now()
    with open(timestamp_file, "r") as f:
        lastread = datetime.fromtimestamp(float(f.read()))
    me = channel.guild.get_member(client.user.id)
    messages = client.logs_from(channel, after=lastread)
    async for message in messages:
        if not message.author == me:
            print_message(message)


async def stream_as_generator(loop, stream):
    reader = asyncio.StreamReader(loop=loop)
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: reader_protocol, stream)

    while True:
        line = await reader.readline()
        if not line:  # EOF.
            break
        yield line


users = []


def get_alias(name, alias_type):
    real_id = name
    for alias in aliases[alias_type]:
        if alias["name"] == name:
            real_id = alias["value"]
    return real_id


def get_channel(identifier):
    return client.get_channel(get_alias(identifier, "channel"))


def get_guild(identifier):
    return client.get_guild(get_alias(identifier, "server"))


async def exit_discord():
    for user in users:
        await user.logout()
        await user.close()


def format_word(word):
    if word.startswith("@"):
        return "<@{}>".format(get_alias(word[1:], "user"))

    if word.startswith("&"):
        return "<@&{}>".format(get_alias(word[1:], "role"))

    if word.startswith("#"):
        return "<#{}>".format(get_alias(word[1:], "channel"))
    return word


async def get_message(channel, message_id):
    logs = client.logs_from(channel, limit=20)
    async for log in logs:
        if log.id == message_id:
            return log


def format_message(message):
    return " ".join([format_word(word) for word in message.split(" ")])


class DiscordCommands:
    def __init__(self):
        self.commands = {}

    def register(self, name=None):
        def wrapper(function):
            new_name = name if name else function.__name__
            self.commands[new_name] = function
            return function
        return wrapper

    async def call(self, client, command):
        tokens = command.split(" ")
        name = tokens[0]
        await self.commands[name](client, *tokens[1:])


commands = DiscordCommands()


@commands.register(name="list")
async def list_command(client, channel=None):
    """ Lists all the messegase since last read """
    if channel:
        channel = get_channel(channel)
    else:
        channel = state.channel
    logs = client.logs_from(channel, limit=20, reverse=True)
    async for log in logs:
        print_message(log)

@commands.register()
async def read(client):
    with open(timestamp_file, "w") as f:
        f.write(str(datetime.utcnow().timestamp()))


@commands.register()
async def guilds(client):
    for guild in client.guilds:
        print("{} - {}".format(guild.id, guild.name))


@commands.register(name="guild")
async def guild_command(client, guild_id=None):
    if not guild_id:
        print(state.guild)
    else:
        state.guild = get_guild(guild_id)

@commands.register()
async def leave(client, guild):
    guild = guild
    await client.leave_guild(get_guild(guild))


@commands.register()
async def channels(client, guild_id=None):
    """ Lists all the channels of a guild """
    
    guild = None
    if guild_id:
        guild = get_guild(guild_id)
    else:
        guild = state.guild

    for channel in guild.channels:
        print("{} - {}".format(channel.id, channel.name))


@commands.register(name="channel")
async def channel_command(client, channel_id=None):
    if not channel_id:
        print(state.channel)
    else:
        state.channel = get_channel(channel_id)

@commands.register()
async def message(client, channel, *message):
    channel = get_channel(channel)
    await client.send_message(channel, format_message(" ".join(message)))


@commands.register()
async def members(client, guild, *args):
    guild = get_guild(guild)
    for member in guild.members:
        if "-r" in args:
            role = args[args.index("-r") + 1]
            role = get_alias(role, "role")
            member_roles = [role.id for role in member.roles]
            if role not in member_roles:
                continue
        nick = member.nick if member.nick else member.name
        print("{} - {}".format(member.mention, nick))


@commands.register()
async def roles(client, guild):
    guild = get_guild(guild)
    for role in guild.roles:
        print("{} - {}".format(role.id, role.name))


@commands.register()
async def user(my_client, user):
    global client
    client = users[int(user)]

@commands.register(name="users")
async def users_command(my_client):
     print("\n".join(
        ["{}: {}".format(
            index,
            client.user.name
        ) for index, client in zip(range(len(users)), users)]))


@commands.register()
async def me(client):
    print(client.user.name)


@commands.register()
async def privates(client):
    for channel in client.private_channels:
        print(
            "{} - [{}]".format(
                channel.id, ", ".join([user.name for user in channel.recipients])
            )
        )
    print(client.user.name)


@commands.register()
async def alias(client, alias_type, alias_name, alias_value):
    aliases[alias_type].append({"name": alias_name, "value": alias_value})
    write_alias_file(aliases)


@commands.register()
async def edit(client, channel, message, to):
    message = await get_message(client.get_channel(channel), message)
    await client.edit_message(message, format_message(" ".join(to)))


async def main_repl():
    global client
    global aliases

    sys.stdout.write("# ")
    sys.stdout.flush()
    state.guild = list(client.guilds)[0]
    state.channel = list(state.guild.channels)[0]
    async for command in stream_as_generator(asyncio.get_event_loop(), sys.stdin):
        try:
            command = command.decode("utf-8").rstrip()
            if command.startswith("/exit"):
                await exit_discord()
                break
            if command.startswith("/"):
                await commands.call(client, command[1:])
            else:
                await client.send_message(state.channel, format_message(command))
            sys.stdout.write("# ")
            sys.stdout.flush()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(e)
            pass

    await exit_discord()


@client.event
async def on_message(message):
    print_message(message)


@client.event
async def on_ready():
    print("Ready for commands")
    await main_repl()


async def main():
    await client.login(AUTH_TOKEN, bot=False)
    global users
    global aliases
    aliases = json.loads(open(aliases_file, "r").read())
    users = [client] + await bots()
    await asyncio.gather(*[bot.connect() for bot in users])


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
