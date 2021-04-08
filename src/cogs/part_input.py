import discord
from discord.ext import commands
from utils import Embed, MessageTimeout, UserCancel
from json import load
import asyncio
from random import choice
from string import ascii_letters, digits


with open("part_spec_models.json") as file:
    part_spec_models = load(file)

input_types = {
    "string": "A single value.",
    "list": "A group of values seperated by a comma."
}

chars = list(ascii_letters + digits)


class PartInput(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        

    def gen_id(self, length):
        return ''.join([choice(chars) for i in range(length)])


    async def assign(self, assign_dict, assign_key, ctx):
        assign_object = {}

        if assign_dict[assign_key].get("_note"):
            embed = Embed(title="Note", description=assign_dict[assign_key]["_note"])
            await ctx.reply(embed=embed)
            await asyncio.sleep(3)

        for category in assign_dict[assign_key]:
            if category.startswith("_"):
                continue

            expected_value = assign_dict[assign_key][category]
            examples = []

            if isinstance(expected_value, str):
                input_type = "string"
                for example in expected_value.split(" | "):
                    examples.append(example)
            elif isinstance(expected_value, list):
                input_type = "list"
                examples.append(', '.join(expected_value))
            else:
                raise ValueError("Invalid example value!")
             
            embed = Embed(title = f"Category: {category}")

            embed.add_field(
                name = "Input Type",
                value = f"`{input_type}` - {input_types[input_type]}",
                inline = False
            )

            embed.add_field(
                name = "Example(s)",
                value = '\n'.join([f"`{example}`" for example in examples]),
                inline = False
            )

            prev_message = await ctx.reply(embed=embed)

            check = lambda m: m.author == ctx.author and m.channel == ctx.channel

            try:
                message = await self.bot.wait_for("message", check=check, timeout=30)
            except asyncio.TimeoutError:
                embed = Embed(title="You took too long to respond! Cancelling submit request.")
                await ctx.reply(embed=embed)
                raise MessageTimeout()
            
            await prev_message.delete()

            if message.content.lower() in ("stop", "exit", "cancel", "terminate", "break", "arrêter"):
                embed = Embed(title="Cancelled part submission")
                await ctx.reply(embed=embed)
                raise UserCancel()

            if message.content.lower() in ("continue", "skip", "next"):
                assign_object[category] = "?"
                continue

            assign_object[category] = message.content

        return assign_object


    @commands.group(invoke_without_command=True, aliases=["pm"], description="Lists all PartMatcher commands.")
    async def partmatcher(self, ctx):
        embed = Embed(
            title = "PartMatcher Commands",
            description = '\n'.join([f"`{command.name}{' ' + command.signature if command.signature else ''}` - {command.description}" for command in self.partmatcher.commands])
        )
        await ctx.send(embed=embed)


    @partmatcher.command(description="Submit a part for verification.")
    async def submit(self, ctx):
        embed = Embed(
            title = "What part type would you like to submit?",
            description = ' '.join([f"`{part}`" for part in part_spec_models if not part.startswith("_")])
        )
        check = lambda m: m.author == ctx.author and m.channel == ctx.channel

        prev_msg = await ctx.reply(embed=embed)
        embed.title = "That's is not a valid part type! Please choose from the below types."

        waiting = True
        while True:
            try:
                message = await self.bot.wait_for("message", check=check, timeout=30)
            except asyncio.TimeoutError:
                embed = Embed(title="You took too long to respond! Cancelling submit request.")
                await ctx.reply(embed=embed)
                return

            for variation in (message.content.capitalize(), message.content.title(), message.content.upper()):
                if variation in part_spec_models:
                    waiting = False
                    break
            
            if not waiting:
                break

            await prev_msg.delete()
            prev_msg = await message.reply(embed=embed)
        
        for count, key in enumerate(("_part", variation)):
            try:
                if count == 0:
                    new_part = await self.assign(part_spec_models, key, ctx)
                else:
                    new_part["specs"] = await self.assign(part_spec_models, key, ctx)
            except (UserCancel, MessageTimeout):
                return

        new_part["Type"] = variation

        while True:
            new_id = self.gen_id(6)
            if not self.bot.db["DiscordBot"]["Submissions"].find_one({"part_id": new_id}):
                new_part["part_id"] = new_id
                self.bot.db["DiscordBot"]["Submissions"].insert_one(new_part)
                break


def setup(bot):
    bot.add_cog(PartInput(bot))