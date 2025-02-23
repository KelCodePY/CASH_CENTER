import os
import telebot
import requests
import json
import asyncio
import logging
from flask import Flask, request

# Configuration
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
COINPAYMENTS_API_KEY = os.getenv("COINPAYMENTS_API_KEY")
COINPAYMENTS_MERCHANT_ID = os.getenv("COINPAYMENTS_MERCHANT_ID")
COINPAYMENTS_IPN_SECRET = os.getenv("COINPAYMENTS_IPN_SECRET")

# Initialisation du bot et du serveur
bot = telebot.AsyncTeleBot(TOKEN)
app = Flask(__name__)

# Configuration des logs
logging.basicConfig(level=logging.INFO, filename="payments.log", format="%(asctime)s - %(message)s")

# Fonction pour récupérer le taux de conversion EUR -> USDT
def get_usdt_price(amount_eur):
    url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=eur"
    response = requests.get(url).json()
    usdt_price = response["tether"]["eur"]
    return round(amount_eur / usdt_price, 2)

# Création d'un paiement
def create_payment(amount, buyer_email):
    amount_usdt = get_usdt_price(amount)
    url = "https://www.coinpayments.net/api.php"
    payload = {
        'cmd': 'create_transaction',
        'key': COINPAYMENTS_API_KEY,
        'version': 1,
        'format': 'json',
        'amount': amount_usdt,
        'currency1': "EUR",
        'currency2': "USDT",
        'buyer_email': buyer_email,
        'merchant': COINPAYMENTS_MERCHANT_ID,
        'ipn_url': "https://votre-site.com/ipn-handler"
    }
    response = requests.post(url, data=payload).json()
    return response

@bot.message_handler(commands=['start'])
async def start(message):
    await bot.send_message(message.chat.id, "Bienvenue sur CASH_CENTER ! Utilisez /buy <montant en EUR> pour effectuer un paiement (minimum 0,25€).")

@bot.message_handler(commands=['buy'])
async def buy(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            await bot.send_message(message.chat.id, "Veuillez spécifier un montant. Exemple : /buy 10")
            return
        amount = float(args[1])
        if amount < 0.25:
            await bot.send_message(message.chat.id, "Le montant minimum est de 0,25€.")
            return
        buyer_email = "user@example.com"  # Peut être demandé à l'utilisateur
        payment = create_payment(amount, buyer_email)
        if payment['error'] == "ok":
            checkout_url = payment['result']['checkout_url']
            await bot.send_message(message.chat.id, f"Payez {amount}€ (≈ {get_usdt_price(amount)} USDT) ici : {checkout_url}")
            logging.info(f"Paiement demandé : {amount} EUR (~{get_usdt_price(amount)} USDT) - Lien : {checkout_url}")
        else:
            await bot.send_message(message.chat.id, f"Erreur: {payment['error']}")
    except ValueError:
        await bot.send_message(message.chat.id, "Montant invalide. Veuillez entrer un nombre valide.")

# Gestion des IPN
@app.route('/ipn-handler', methods=['POST'])
def ipn_handler():
    data = request.form.to_dict()
    if data.get("ipn_secret") == COINPAYMENTS_IPN_SECRET:
        if data.get("status") == "100":  # Paiement confirmé
            logging.info(f"Paiement confirmé : {data}")
            bot.send_message(data['buyer_email'], "Votre paiement a été reçu avec succès ! Merci.")
        return "OK", 200
    return "Non autorisé", 403

# Lancement du bot et du serveur Flask
if __name__ == "__main__":
    from threading import Thread
    Thread(target=lambda: asyncio.run(bot.polling(none_stop=True))).start()
    app.run(host="0.0.0.0", port=10000)
