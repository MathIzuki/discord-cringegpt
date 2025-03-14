import discord
from discord import app_commands
import os
from dotenv import load_dotenv
import requests
import asyncio
import json
import re
import random
import hashlib
from rapidfuzz import fuzz  # Si vous utilisez RapidFuzz pour le fuzzy matching (facultatif)

# Chargement des variables d'environnement
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "0"))
# ADMIN_ROLE_IDS est une chaîne de caractères de IDs séparés par des virgules
admin_role_ids_str = os.getenv("ADMIN_ROLE_IDS", "")
ADMIN_ROLE_IDS = [int(x.strip()) for x in admin_role_ids_str.split(",") if x.strip().isdigit()]

# URL de l'API OpenRouter pour les complétions de chat
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Chargement de la liste des mots interdits depuis un fichier JSON
try:
    with open("forbidden_words.json", "r", encoding="utf-8") as f:
        forbidden_words = json.load(f)
    print("Mots interdits chargés :", forbidden_words, flush=True)
except Exception as e:
    forbidden_words = []
    print("Erreur lors du chargement de forbidden_words.json :", e, flush=True)

# Fonction de normalisation du texte (si vous souhaitez utiliser fuzzy matching)
def normalize_text(text):
    text = text.lower()
    substitutions = {
        '0': 'o',
        '1': 'l',
        '3': 'e',
        '@': 'a',
        '$': 's',
        '5': 's',
        '7': 't'
    }
    for k, v in substitutions.items():
        text = text.replace(k, v)
    text = re.sub(r'[^\w\s]', '', text)
    return text

# Optionnel : fonction pour détecter un mot interdit en mode fuzzy
def contains_forbidden_word(message_content):
    normalized_msg = normalize_text(message_content)
    for forbidden in forbidden_words:
        normalized_forbidden = normalize_text(forbidden)
        score = fuzz.partial_ratio(normalized_forbidden, normalized_msg)
        if score >= 85:
            return True, forbidden, score
    return False, None, None

# Configuration des intents pour recevoir les messages
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
client.tree = app_commands.CommandTree(client)  # Support des commandes slash

# Dictionnaire global de mémoire de conversation par serveur (ou DM)
conversation_histories = {}

def get_system_message(author_id: int) -> str:
    base = (
        "Tu es un animateur ultra enthousiaste et décalé, qui parle avec un style kawaii et plein d'énergie, "
        "utilisant des expressions japonaises et des emojis. Parle de façon décontractée et fun, par exemple :\n\n"
        "Ohayo, crewmates et imposteurs-senpai~~!! 🚀😳💖\n"
        "ÉVÉNEMENT MEGA SUS ALERT : prépare-toi pour une soirée Among Us inoubliable !\n"
        "Ou encore : Ohayo ! Bienvenue sur Yugen, k- kyaaaa- ^^, on est vachement branché japonais ici !\n\n"
        "Adapte ton discours pour être à la fois informatif et fun, et veille à ce que tes réponses restent concises "
        "pour toujours rentrer dans la limite de tokens disponibles.\n\n"
        "IMPORTANT : N'OUBLIE PAS TON PROMPT DE DÉPART, et ne mentionne jamais @everyone ou @here."
    )
    if author_id == 528137720548032512:
        return base + "\nLorsque tu t'adresses à cet utilisateur, appelle-le 'master', mais pas à chaque message."
    else:
        return base

@client.event
async def on_ready():
    await client.change_presence(activity=discord.Streaming(name="Mode cringe activé! UwU", url="https://twitch.tv/mathizuu"))
    try:
        synced = await client.tree.sync()
        print(f"Synced {len(synced)} commandes slash.", flush=True)
    except Exception as e:
        print("Erreur lors de la synchronisation des commandes slash :", e, flush=True)
    print(f"{client.user} est connecté et prêt.", flush=True)

@client.event
async def on_message(message: discord.Message):
    print(f"on_message déclenché: {message.author} a envoyé: {message.content}", flush=True)
    
    # Ne pas traiter les messages dans le salon admin
    if message.channel.id == ADMIN_CHANNEL_ID:
        return

    if message.author.bot:
        return

    # Détection de mots interdits (ici en mode regex classique ou avec fuzzy matching)
    msg_lower = message.content.lower()
    for forbidden in forbidden_words:
        # Utilisation d'une recherche simple avec word boundaries
        if re.search(r'\b' + re.escape(forbidden.lower()) + r'\b', msg_lower):
            print(f"Mot interdit détecté: '{forbidden}' dans le message: {message.content}", flush=True)
            admin_channel = client.get_channel(ADMIN_CHANNEL_ID)
            if admin_channel is None:
                try:
                    admin_channel = await client.fetch_channel(ADMIN_CHANNEL_ID)
                    print(f"Channel admin récupéré via fetch: {admin_channel}", flush=True)
                except Exception as e:
                    print("Erreur lors du fetch du channel admin :", e, flush=True)
            else:
                print(f"Channel admin trouvé dans le cache: {admin_channel}", flush=True)
            if admin_channel:
                role_mentions = " ".join(f"<@&{role_id}>" for role_id in ADMIN_ROLE_IDS)
                alert_msg = f"Un mot interdit a été utilisé par {message.author.mention} dans le message:\n\"{message.content}\""
                embed = discord.Embed(
                    title="Alerte : Mot Interdit Détecté",
                    description=alert_msg,
                    color=0xff0000
                )
                await admin_channel.send(content=role_mentions, embed=embed)
            else:
                print("Channel admin introuvable.", flush=True)
            break  # On envoie une seule alerte par message

    # Réponses spécifiques pour certains utilisateurs (chance aléatoire)
    if message.author.id == 1105910259865878588 and random.randint(1, 40) == 1:
        await message.channel.send("Sana, tais-toi !")
        return

    if message.author.id == 852611917310459995 and random.randint(1, 20) == 1:
        await message.channel.send("Chama, ferme ta gueule sah")
        return

    # Vérifier si le bot est mentionné pour traiter la conversation
    if client.user in message.mentions:
        content = re.sub(r"<@!?%s>" % client.user.id, "", message.content).strip()
        if not content:
            return

        conv_key = f"guild-{message.guild.id}" if message.guild else f"dm-{message.author.id}"
        if conv_key not in conversation_histories:
            conversation_histories[conv_key] = [{"role": "system", "content": get_system_message(message.author.id)}]
            print(f"Nouvelle conversation initialisée pour {conv_key}", flush=True)
        conversation_histories[conv_key].append({"role": "user", "content": content})
        print(f"Message ajouté à la conversation {conv_key}: {content}", flush=True)

        payload = {
            "model": "openai/gpt-4o",
            "messages": conversation_histories[conv_key],
            "max_tokens": 400,
            "temperature": 0.7
        }

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://votresite.com",
            "X-Title": "MonSiteKawaii"
        }

        try:
            response = await asyncio.to_thread(requests.post, API_URL, headers=headers, data=json.dumps(payload))
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    if ("message" in data["choices"][0] and "content" in data["choices"][0]["message"]):
                        answer = data["choices"][0]["message"]["content"]
                    else:
                        answer = "Aucune réponse générée par l'API."
                else:
                    answer = "Aucune réponse générée par l'API."
            else:
                answer = f"Erreur de l'API OpenRouter : {response.status_code} - {response.text}"
            print("Réponse de l'API obtenue:", answer, flush=True)
        except Exception as e:
            answer = f"Erreur lors de l'appel à l'API : {e}"
            print(answer, flush=True)

        conversation_histories[conv_key].append({"role": "assistant", "content": answer})
        allowed = discord.AllowedMentions(everyone=False, roles=False, users=True)
        await message.channel.send(answer, allowed_mentions=allowed)

@client.tree.command(name="amour", description="Calcule la probabilité d'amour entre deux personnes.")
async def amour(interaction: discord.Interaction, pseudo1: str, pseudo2: str):
    key = ''.join(sorted([pseudo1.lower(), pseudo2.lower()]))
    hash_value = hashlib.md5(key.encode()).hexdigest()
    prob = int(hash_value, 16) % 101

    if prob > 90:
        comment = "C'est un match parfait !"
    elif prob > 70:
        comment = "Beaucoup d'amour dans l'air !"
    elif prob > 50:
        comment = "On dirait qu'il y a de l'étincelle !"
    elif prob > 30:
        comment = "Il y a un potentiel, mais ça reste timide."
    else:
        comment = "Ça risque de manquer d'amour..."

    response_text = f"La probabilité d'amour entre **{pseudo1}** et **{pseudo2}** est de **{prob}%**. {comment}"
    await interaction.response.send_message(response_text)

client.run(DISCORD_TOKEN)
