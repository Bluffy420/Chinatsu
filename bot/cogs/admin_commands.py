import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from ..database.models import ServerSettings, UserRelations
from ..config import OWNER_ID

class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    def _check_admin(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions"""
        if not interaction.guild:
            return False
        return (
            interaction.user.guild_permissions.administrator or
            interaction.user.id == OWNER_ID
        )
        
    @app_commands.command(name="activate")
    async def activate_server(self, interaction: discord.Interaction):
        """Activate the bot for this server"""
        if not self._check_admin(interaction):
            await interaction.response.send_message("❌ You need administrator permissions for this command.", ephemeral=True)
            return
            
        try:
            ServerSettings.execute_query(
                "INSERT OR REPLACE INTO server_activation (server_id, active) VALUES (?, 1)",
                (str(interaction.guild_id),)
            )
            await interaction.response.send_message("✅ Bot activated for this server!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ Failed to activate bot. Please try again.", ephemeral=True)
            
    @app_commands.command(name="deactivate")
    async def deactivate_server(self, interaction: discord.Interaction):
        """Deactivate the bot for this server"""
        if not self._check_admin(interaction):
            await interaction.response.send_message("❌ You need administrator permissions for this command.", ephemeral=True)
            return
            
        try:
            ServerSettings.execute_query(
                "INSERT OR REPLACE INTO server_activation (server_id, active) VALUES (?, 0)",
                (str(interaction.guild_id),)
            )
            await interaction.response.send_message("✅ Bot deactivated for this server!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("❌ Failed to deactivate bot. Please try again.", ephemeral=True)
            
    @app_commands.command(name="filter")
    @app_commands.describe(
        action="Action to perform",
        guild_id="Server ID to apply the filter setting to (optional, defaults to current server)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable")
    ])
    async def manage_filter(
        self,
        interaction: discord.Interaction,
        action: str,
        guild_id: Optional[str] = None
    ):
        """Manage content filter settings"""
        if not self._check_admin(interaction):
            await interaction.response.send_message("❌ You need administrator permissions for this command.", ephemeral=True)
            return
            
        target_guild = guild_id or str(interaction.guild_id)
        filter_enabled = 1 if action == "enable" else 0
        
        try:
            ServerSettings.execute_query(
                """
                INSERT INTO filter_settings (server_id, filter_enabled)
                VALUES (?, ?)
                ON CONFLICT(server_id) DO UPDATE SET
                    filter_enabled = excluded.filter_enabled,
                    last_updated = CURRENT_TIMESTAMP
                """,
                (target_guild, filter_enabled)
            )
            
            status = "enabled" if filter_enabled else "disabled"
            await interaction.response.send_message(
                f"✅ Content filter {status} for server {target_guild}!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message("❌ Failed to update filter settings. Please try again.", ephemeral=True)
            
    @app_commands.command(name="mature_content")
    @app_commands.describe(
        action="Action to take with mature content",
        level="Intensity level (1=mild, 2=moderate, 3=advanced)",
        guild_id="Server ID to apply the setting to (optional, defaults to current server)"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="enable", value="enable"),
            app_commands.Choice(name="disable", value="disable")
        ],
        level=[
            app_commands.Choice(name="mild", value=1),
            app_commands.Choice(name="moderate", value=2),
            app_commands.Choice(name="advanced", value=3)
        ]
    )
    async def manage_mature_content(
        self,
        interaction: discord.Interaction,
        action: str,
        level: int = 1,
        guild_id: Optional[str] = None
    ):
        """Manage mature content settings"""
        if not self._check_admin(interaction):
            await interaction.response.send_message("❌ You need administrator permissions for this command.", ephemeral=True)
            return
            
        if not interaction.channel.is_nsfw():
            await interaction.response.send_message("❌ This command can only be used in NSFW channels.", ephemeral=True)
            return
            
        target_guild = guild_id or str(interaction.guild_id)
        mature_enabled = 1 if action == "enable" else 0
        
        try:
            ServerSettings.execute_query(
                """
                INSERT INTO filter_settings 
                (server_id, mature_enabled, mature_level)
                VALUES (?, ?, ?)
                ON CONFLICT(server_id) DO UPDATE SET
                    mature_enabled = excluded.mature_enabled,
                    mature_level = excluded.mature_level,
                    last_updated = CURRENT_TIMESTAMP
                """,
                (target_guild, mature_enabled, level)
            )
            
            status = "enabled" if mature_enabled else "disabled"
            level_text = ["mild", "moderate", "advanced"][level-1]
            await interaction.response.send_message(
                f"✅ Mature content {status} (level: {level_text}) for server {target_guild}!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message("❌ Failed to update mature content settings. Please try again.", ephemeral=True)
            
    @app_commands.command(name="adjust_honor")
    @app_commands.describe(
        user_id="User ID to adjust honor for",
        amount="Amount to adjust (positive or negative)"
    )
    async def adjust_honor(
        self,
        interaction: discord.Interaction,
        user_id: str,
        amount: int
    ):
        """Adjust a user's honor/reputation"""
        if not self._check_admin(interaction):
            await interaction.response.send_message("❌ You need administrator permissions for this command.", ephemeral=True)
            return
            
        try:
            # Get current user data
            user_data = UserRelations.get_user(int(user_id))
            new_reputation = user_data["reputation"] + amount
            
            # Update reputation
            UserRelations.execute_query(
                """
                UPDATE relations_users
                SET reputation = ?,
                    last_interaction = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (new_reputation, int(user_id))
            )
            
            await interaction.response.send_message(
                f"✅ Adjusted honor for user {user_id} by {amount} (new total: {new_reputation})",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message("❌ Failed to adjust honor. Please try again.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommands(bot)) 