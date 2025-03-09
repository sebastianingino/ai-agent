from actions.task import (
    TaskDeadline,
    TaskDelete,
    TaskList,
    TaskListAll,
    TaskMark,
    TaskNew,
)
from arguments.parser import ArgParser
from commands.command import command, CommandContext
from mistral.chat import Chat
from util.util import preflight_execute


@command("Task", "Manage tasks")
async def task_entry(ctx: CommandContext, *args: str):
    if len(args) > 0:
        return await ctx.reply(
            "Sorry, I don't understand that command. Use `!task help` to see a list of available commands."
        )
    return await ctx.reply(await Chat.help(ctx.command_stack[-1].helptext() or ""))


@command("List", "List tasks", parent=task_entry)
async def task_list(ctx: CommandContext, *args: str):
    parser = ArgParser()
    parser.add_argument("project", "p")
    parser.parse(args)
    project = parser.project or " ".join(args) if len(args) > 0 else None
    action = TaskList(project=project)
    async with ctx.message.channel.typing():
        return await ctx.reply(await preflight_execute(action, ctx))


@command("All", "List all tasks", parent=task_entry)
async def task_all(ctx: CommandContext, *args: str):
    action = TaskListAll()
    async with ctx.message.channel.typing():
        return await ctx.reply(await preflight_execute(action, ctx))


@command("New", "Create a new task", parent=task_entry)
async def task_new(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!task new [name] (-p <project>)`")
    parser = ArgParser()
    parser.add_argument("project", "p")
    name = parser.parse(args)
    project = parser.project

    action = TaskNew(name=name, project=project)
    return await ctx.reply(await preflight_execute(action, ctx))


@command("Mark", "Mark a task as done", parent=task_entry)
async def task_mark(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!task mark [task] (-p <project>)`")
    parser = ArgParser()
    parser.add_argument("project", "p")
    task = parser.parse(args)
    project = parser.project
    action = TaskMark(task=task, project=project, status=True)
    return await ctx.reply(await preflight_execute(action, ctx))


@command("Unmark", "Unmark a task as done", parent=task_entry)
async def task_unmark(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!task unmark [task] (-p <project>)`")
    parser = ArgParser()
    parser.add_argument("project", "p")
    task = parser.parse(args)
    project = parser.project
    action = TaskMark(task=task, project=project, status=False)
    return await ctx.reply(await preflight_execute(action, ctx))


@command("Delete", "Delete a task", parent=task_entry)
async def task_delete(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply("Usage: `!task delete [task] (-p <project>)`")
    parser = ArgParser()
    parser.add_argument("project", "p")
    task = parser.parse(args)
    project = parser.project
    action = TaskDelete(task=task, project=project)
    return await ctx.reply(await preflight_execute(action, ctx))


@command("Deadline", "Set a deadline for a task", parent=task_entry)
async def task_deadline(ctx: CommandContext, *args: str):
    if len(args) < 1:
        return await ctx.reply(
            "Usage: `!task deadline [task] -d [deadline] (-p <project>)`"
        )
    parser = ArgParser()
    parser.add_argument("project", "p")
    parser.add_argument("deadline", "d")
    task = parser.parse(args)
    project = parser.project
    deadline = parser.deadline
    if not deadline:
        return await ctx.reply(
            "Usage: `!task deadline [task] -d [deadline] (-p <project>)`"
        )
    action = TaskDeadline(task=task, project=project, when=deadline)
    return await ctx.reply(await preflight_execute(action, ctx))
