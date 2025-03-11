from commands.command import command, CommandContext
from mistral.agent import Agent
from util import messages


@command("Ask", "Ask a question to the bot")
async def ask_entry(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return ctx.reply("Usage: `!ask [anything]`")
    message = ctx.message
    async with message.channel.typing():
        response = await Agent.handle(message, [], ctx.bot)
        if not response:
            return

        # Send the response back to the channel
        for chunk in messages.chunkify(response):
            message = await message.reply(chunk)
