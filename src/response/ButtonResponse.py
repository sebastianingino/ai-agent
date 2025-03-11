from typing import Any, Callable, Coroutine, Optional, Union, override
from discord.ui import View, Button as DiscordButton
from discord import ButtonStyle, Interaction, Member, User

Callback = Callable[[Interaction], Coroutine[Any, Any, Any]]


class Button(DiscordButton):

    def __init__(
        self,
        label: str,
        style: ButtonStyle,
        callback: Optional[Callback] = None,
        user: Optional[Union[User, Member]] = None,
        reverse: bool = False,
    ):
        super().__init__(label=label, style=style)
        self._callback = callback
        self.user = user
        self.reverse = reverse
        self.called = False

    @override
    async def interaction_check(self, interaction: Interaction) -> bool:
        if self.user is not None:
            return interaction.user.id == self.user.id
        return True

    @override
    async def callback(self, interaction: Interaction):
        if self.reverse:
            if self.view is not None:
                self.view.stop()
            if interaction.message is not None:
                await interaction.message.edit(view=None)
            if self._callback is not None and not self.called:
                self.called = True
                await self._callback(interaction)
        else:
            if self._callback is not None and not self.called:
                self.called = True
                await self._callback(interaction)
            if self.view is not None:
                self.view.stop()
            if interaction.message is not None:
                await interaction.message.edit(view=None)


async def default_neg(interaction: Interaction):
    await interaction.response.send_message("Cancelled", ephemeral=True)


def binary_response(
    pos_callback: Callback,
    neg_callback: Callback = default_neg,
    pos_text: str = "Confirm",
    neg_text: str = "Cancel",
    timeout: Optional[int] = None,
    user: Optional[Union[User, Member]] = None,
    reverse: bool = False,
):
    """
    Create a binary response.
    """
    pos_button: Button = Button(
        label=pos_text,
        style=ButtonStyle.success,
        callback=pos_callback,
        user=user,
        reverse=reverse,
    )
    neg_button: Button = Button(
        label=neg_text,
        style=ButtonStyle.danger,
        callback=neg_callback,
        user=user,
        reverse=reverse,
    )
    view = View(timeout=timeout)
    view.add_item(pos_button)
    view.add_item(neg_button)
    return view
