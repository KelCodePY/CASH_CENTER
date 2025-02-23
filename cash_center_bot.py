import os
import telebot
import requests
import json
import logging
from flask import Flask, request
from threading import Thread

# 🔥 Configuration
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
COINPAYMENTS_API_KEY = os.getenv("COINPAYMENTS_API_KEY")
COINPAYMENTS_MERCHANT_ID = os.getenv("COINPAYMENTS_MERCHANT_ID")
COINPAYMENTS_IPN_SECRET = os.getenv("COINPAYMENTS_IPN_SECRET")

# Initialisation du bot et du serveur
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# 📜 Configuration des logs
logging.basicConfig(level=logging.INFO, filename="payments.log", format="%(asctime)s - %(message)s")

# 💰 Fonction pour récupérer le taux de conversion EUR -> USDT
def get_usdt_price(amount_eur):
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=eur"
        response = requests.get(url).json()
        usdt_price = response["tether"]["eur"]
        return round(amount_eur / usdt_price, 2)
    except Exception as e:
        logging.error(f"Erreur récupération prix USDT : {e}")
        return None

# 🔗 Création d'un paiement
def create_payment(amount, buyer_email):
    amount_usdt = get_usdt_price(amount)
    if amount_usdt is None:
        return {"error": "Impossible de récupérer le taux de change."}

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

# 🎉 Commande /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Bienvenue sur CASH_CENTER !\nUtilisez /buy <montant en EUR> pour effectuer un paiement (minimum 0,25€).")

# 🛒 Commande /buy
@bot.message_handler(commands=['buy'])
def buy(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.send_message(message.chat.id, "Veuillez spécifier un montant. Exemple : /buy 10")
            return

        amount = float(args[1])
        if amount < 0.25:
            bot.send_message(message.chat.id, "Le montant minimum est de 0,25€.")
            return

        # Demander l'email utilisateur
        msg = bot.send_message(message.chat.id, "Veuillez entrer votre email pour recevoir la confirmation du paiement :")
        bot.register_next_step_handler(msg, process_email, amount)

    except ValueError:
        bot.send_message(message.chat.id, "Montant invalide. Veuillez entrer un nombre valide.")

# 📧 Traitement de l'email utilisateur
def process_email(message, amount):
    buyer_email = message.text
    payment = create_payment(amount, buyer_email)

    if payment['error'] == "ok":
        checkout_url = payment['result']['checkout_url']
        bot.send_message(message.chat.id, f"Payez {amount}€ (≈ {get_usdt_price(amount)} USDT) ici : {checkout_url}")
        logging.info(f"Paiement demandé : {amount} EUR (~{get_usdt_price(amount)} USDT) - Lien : {checkout_url}")
    else:
        bot.send_message(message.chat.id, f"Erreur: {payment['error']}")

# 🔄 Gestion des IPN (notifications de paiement)
@app.route('/ipn-handler', methods=['POST'])
def ipn_handler():
    data = request.form.to_dict()
    
    if data.get("ipn_secret") == COINPAYMENTS_IPN_SECRET:
        if data.get("status") == "100":  # Paiement confirmé
            logging.info(f"✅ Paiement confirmé : {data}")
            bot.send_message(data['buyer_email'], "✅ Votre paiement a été reçu avec succès ! Merci.")
        elif data.get("status") == "-1":  # Paiement annulé
            logging.warning(f"❌ Paiement annulé : {data}")
        return "OK", 200

    return "Non autorisé", 403

# 🚀 Lancement du bot et du serveur Flask
def run_bot():
    bot.polling(none_stop=True)

if __name__ == "__main__":
    # Démarrage du bot Telegram dans un thread séparé
    Thread(target=run_bot).start()
    
    # Démarrage du serveur Flask
    app.run(host="0.0.0.0", port=10000)
