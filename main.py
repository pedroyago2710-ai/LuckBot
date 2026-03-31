import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime
import motor.motor_asyncio

# --- CONFIG ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=".", intents=intents)

# --- MONGODB ---
@bot.event
async def on_ready():
    try:
        uri = os.getenv("MONGO_URI")

        if not uri:
            print("❌ MONGO_URI não encontrada!")
            return

        bot.db_client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        bot.db = bot.db_client['rage_database']

        print(f"✅ Bot online como {bot.user}")
        print("✅ MongoDB conectado!")

    except Exception as e:
        print(f"❌ Erro MongoDB: {e}")

# --- PERFIL ---
async def get_user_data(user_id):
    if not hasattr(bot, "db"):
        return {"wins": 0, "losses": 0, "coins": 0}

    user = await bot.db.users.find_one({"_id": str(user_id)})
    if not user:
        user = {"_id": str(user_id), "wins": 0, "losses": 0, "coins": 0}
        await bot.db.users.insert_one(user)
    return user

@bot.command()
async def perfil(ctx, membro: discord.Member = None):
    membro = membro or ctx.author
    data = await get_user_data(membro.id)

    total = data['wins'] + data['losses']
    winrate = (data['wins'] / total * 100) if total > 0 else 0

    embed = discord.Embed(title=f"👤 Perfil de {membro.name}", color=0x2f3136)
    embed.add_field(name="🏆 Vitórias", value=f"`{data['wins']}`")
    embed.add_field(name="💀 Derrotas", value=f"`{data['losses']}`")
    embed.add_field(name="📈 Winrate", value=f"`{winrate:.1f}%`")
    embed.add_field(name="💰 Coins", value=f"`{data['coins']}`")

    await ctx.send(embed=embed)

# --- BLACKLIST ---
@bot.command()
@commands.has_permissions(administrator=True)
async def blackadd(ctx, user_id: str, *, motivo: str):
    if not hasattr(bot, "db"):
        return await ctx.send("❌ Banco offline")

    await bot.db.blacklist.update_one(
        {"_id": user_id},
        {"$set": {"motivo": motivo, "data": datetime.now()}},
        upsert=True
    )

    await ctx.send(f"✅ ID `{user_id}` adicionado à blacklist.")

# --- PEDIR SS ---
@bot.command()
async def pedir_ss(ctx, tipo: str, aposta: str):
    embed = discord.Embed(title="🆘 Solicitação SS", color=0xff0000)
    embed.add_field(name="Tipo", value=tipo)
    embed.add_field(name="Mediador", value=ctx.author.mention)
    embed.add_field(name="Aposta", value=f"#{aposta}")
    embed.description = "Um analista pode assumir manualmente."

    await ctx.send(embed=embed)

# --- LOJINHA ---
@bot.command()
async def lojinha(ctx):
    embed = discord.Embed(
        title="🛒 RN SYSTEM SHOP",
        description="Use seus coins!",
        color=0x00ff7f
    )

    embed.add_field(name="🎁 Exemplo 1", value="5 coins", inline=False)
    embed.add_field(name="👑 VIP Mensal", value="50 coins", inline=False)

    await ctx.send(embed=embed)

# --- START ---
async def main():
    await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
