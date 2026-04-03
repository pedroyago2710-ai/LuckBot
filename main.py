import discord
from discord.ext import commands
import json
import os
import qrcode
from pymongo import MongoClient
import os

MONGO_URL = os.getenv("MONGO_URL")

client = MongoClient(MONGO_URL)
db = client["discord_bot"]

filas_db = db["filas"]
pix_db = db["pix"]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------ ARQUIVOS ------------------

ARQ_FILAS = "filas.json"
ARQ_PIX = "pix.json"

def load_json(path):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

filas = load_json(ARQ_FILAS)
pix_db = load_json(ARQ_PIX)

# ------------------ EMBED FILA ------------------

def criar_embed(fila_id):
    fila = filas[fila_id]

    jogadores = fila["jogadores"]
    lista = "\n".join([f"{i+1}. <@{j}>" for i, j in enumerate(jogadores)])
    if not lista:
        lista = "Nenhum jogador na fila"

    embed = discord.Embed(
        title=fila["nome"],
        color=discord.Color.dark_gray()
    )

    embed.add_field(name="🎮 Estilo", value=fila["estilo"], inline=False)
    embed.add_field(name="💰 Valor", value=fila["valor"], inline=False)
    embed.add_field(name="👥 Jogadores", value=lista, inline=False)

    if fila["banner"]:
        embed.set_image(url=fila["banner"])

    if fila["thumb"]:
        embed.set_thumbnail(url=fila["thumb"])

    return embed

# ------------------ PARTIDA ------------------

class PartidaView(discord.ui.View):
    def __init__(self, fila_id):
        super().__init__(timeout=None)
        self.confirmados = []
        self.fila_id = fila_id

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.green)
    async def confirmar(self, interaction: discord.Interaction, button):
        if interaction.user.id not in self.confirmados:
            self.confirmados.append(interaction.user.id)

        lista = "\n".join([f"<@{i}>" for i in self.confirmados])

        embed = discord.Embed(
            title="Partida",
            description=f"**Confirmados:**\n{lista}",
            color=discord.Color.red()
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.red)
    async def cancelar(self, interaction: discord.Interaction, button):
        await interaction.channel.delete()

# ------------------ CRIAR CANAL ------------------

async def criar_canal(interaction, fila_id):

    fila = filas[fila_id]
    guild = interaction.guild

    mediador = discord.utils.get(guild.roles, name="Mediador")
    log_channel = discord.utils.get(guild.text_channels, name="logs")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False)
    }

    membros = []

    for user_id in fila["jogadores"]:
        membro = guild.get_member(user_id)
        if membro:
            overwrites[membro] = discord.PermissionOverwrite(view_channel=True)
            membros.append(membro)

    if mediador:
        overwrites[mediador] = discord.PermissionOverwrite(view_channel=True)

    canal = await guild.create_text_channel(
        name=f"fila-{fila_id}",
        overwrites=overwrites
    )

    await canal.send(
        content=" ".join([m.mention for m in membros]),
        embed=discord.Embed(
            title=f"{fila['nome']} | {fila['valor']}",
            description="Confirmados:\nNenhum ainda.",
            color=discord.Color.red()
        ),
        view=PartidaView(fila_id)
    )

    if log_channel:
        await log_channel.send(
            f"📢 Nova partida criada: {fila['nome']} com {len(membros)} jogadores."
        )

    fila["jogadores"] = []
    save_json(ARQ_FILAS, filas)

# ------------------ FILA VIEW ------------------

class FilaView(discord.ui.View):

    def __init__(self, fila_id):
        super().__init__(timeout=None)
        self.fila_id = fila_id

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green)
    async def entrar(self, interaction: discord.Interaction, button):
        fila = filas[self.fila_id]

        if interaction.user.id not in fila["jogadores"]:
            fila["jogadores"].append(interaction.user.id)

        save_json(ARQ_FILAS, filas)

        if len(fila["jogadores"]) >= fila["max"]:
            await criar_canal(interaction, self.fila_id)

        await interaction.response.edit_message(
            embed=criar_embed(self.fila_id),
            view=self
        )

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, interaction: discord.Interaction, button):
        fila = filas[self.fila_id]

        if interaction.user.id in fila["jogadores"]:
            fila["jogadores"].remove(interaction.user.id)

        save_json(ARQ_FILAS, filas)

        await interaction.response.edit_message(
            embed=criar_embed(self.fila_id),
            view=self
        )

# ------------------ CRIAR FILA ------------------

@bot.command()
async def criarfila(ctx, nome, valor, estilo, tamanho: int):

    fila_id = str(len(filas) + 1)

    filas[fila_id] = {
        "nome": nome,
        "valor": valor,
        "estilo": estilo,
        "tamanho": tamanho,
        "jogadores": [],
        "banner": "",
        "thumb": ""
    }

    save_json(ARQ_FILAS, filas)

    await ctx.send(embed=criar_embed(fila_id), view=FilaView(fila_id))

# ------------------ PIX MODAL ------------------

class PixModal(discord.ui.Modal, title="Cadastrar Pix"):

    nome = discord.ui.TextInput(label="Seu nome")
    chave = discord.ui.TextInput(label="Chave Pix")

    async def on_submit(self, interaction: discord.Interaction):

        pix_db[str(interaction.user.id)] = {
            "nome": self.nome.value,
            "chave": self.chave.value
        }

        save_json(ARQ_PIX, pix_db)

        await interaction.response.send_message(
            "✅ Pix cadastrado!",
            ephemeral=True
        )

# ------------------ PIX VIEW (BOTÃO COPIAR) ------------------

class PixView(discord.ui.View):

    def __init__(self, chave):
        super().__init__()
        self.chave = chave

    @discord.ui.button(label="Copiar Chave", style=discord.ButtonStyle.gray)
    async def copiar(self, interaction: discord.Interaction, button):
        await interaction.response.send_message(
            f"🔑 Copie sua chave:\n`{self.chave}`",
            ephemeral=True
        )

# ------------------ SLASH COMMANDS ------------------

@bot.tree.command(name="cadastrar_pix")
async def cadastrar_pix(interaction: discord.Interaction):
    await interaction.response.send_modal(PixModal())

@bot.tree.command(name="pix_valor")
async def pix_valor(interaction: discord.Interaction, valor: str):

    user_id = str(interaction.user.id)

    if user_id not in pix_db:
        await interaction.response.send_message(
            "❌ Cadastre seu Pix primeiro!",
            ephemeral=True
        )
        return

    dados = pix_db[user_id]

    chave = dados["chave"]
    nome = dados["nome"]

    img = qrcode.make(chave)
    caminho = f"qrcode_{user_id}.png"
    img.save(caminho)

    file = discord.File(caminho, filename="qrcode.png")

    embed = discord.Embed(
        title="💰 Pagamento via Pix",
        description=(
            f"👤 Mediador: {nome}\n"
            f"🔑 Chave: {chave}\n"
            f"💵 Valor: R$ {valor}"
        ),
        color=discord.Color.red()
    )

    embed.set_image(url="attachment://qrcode.png")

    await interaction.response.send_message(
        embed=embed,
        file=file,
        view=PixView(chave)
    )

# ------------------ READY ------------------

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logado como {bot.user}")

bot.run("SEU_TOKEN")
