# -*- coding: utf-8 -*-

from flask import Flask, render_template, request
import json
import os
import requests
import webbrowser

# initialisation de l'application Flask
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

# permet de créer et afficher la page d'accueil du site de recommandation de livres 
@app.route('/')
def home():
    return render_template('index.html')

# partie qui permet d'afficher la liste des livres présents dans le fichier JSON 
@app.route('/livres')
def livres():
    with open('static/livres.json', 'r', encoding='utf-8-sig') as f:
        livres_data = json.load(f)
    return render_template('livres.html', livres=livres_data)

# fonction qui permet de faire une recommandation des livres, elle filtre les livres selon un genre qui est passé en paramètre. 
@app.route('/recommandation')
def recommandation():
    genre = request.args.get('genre')
    with open('static/livres.json', 'r', encoding='utf-8-sig') as f:
        livres_data = json.load(f)
    livres_recommandes = [livre for livre in livres_data if livre['genre'] == genre]
    return render_template('livres.html', livres=livres_recommandes)

# fonction qui permet de rechercher le livre passé en paramètre via l'url, et permet de retourner les informations sur ce livre
def rechercher_livre(nom_livre):
    url = f"https://www.googleapis.com/books/v1/volumes?q={nom_livre}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['items'][0]['volumeInfo']
    return None

# fonction qui appelle le modèle Mistral hébergé sur le token Hugging Face; elle envoie un prompt et récupère le résumé du livre. 
def appeler_huggingface(prompt):
    url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"

    headers = {
        "Authorization": "Bearer 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",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": f"[INST] {prompt} [/INST]",
        "parameters": {
            "max_new_tokens": 300,
            "temperature": 0.7
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        result = response.json()
        return result[0]['generated_text']
    else:
        return f"Erreur Hugging Face : {response.status_code} - {response.text}"

# fonction qui permet de rechercher un livre à partir de plusieurs critères (titre, auteur, genre et édition)
@app.route('/find')
def find():
    # récupération des paramètres depuis l'url 
    nom_livre = request.args.get('nomlivre')
    auteur = request.args.get('auteur')
    genre = request.args.get('genre')
    edition = request.args.get('edition')

    if not nom_livre and not auteur and not genre and not edition:
        return "Aucun nom de livre fourni.", 400

    # création du prompt en langage naturel pour le modèle Mistral avec tous les éléments renseignés
    prompt = f"Donne-moi les details du livre intitule '{nom_livre}'"
    if auteur:
        prompt += f", ecrit par {auteur}"
    if genre:
        prompt += f", dans le genre {genre}"
    if edition:
        prompt += f", publie par {edition}"
    prompt += ". Resume le contenu, donne l'auteur, le genre et l'edition si possible."

    reponse = appeler_huggingface(prompt)

    # affiche la réponse dans le template livres.html
    return render_template('livres.html', reponse=reponse)

# ouvre automatiquement le navigateur sur la page d'accueil 
if __name__ == '__main__':
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True)

# fonction qui permet de mettre en forme le site pour avoir une discussion avec l'IA expertes en livres sur un livre en particulier et va pouvoir faire une recommandation de quelques livres qui ressemblent à ce livre
@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get("message", "")
    
    if not user_message:
        return jsonify({"reponse": "Je n'ai pas compris. Peux-tu reformuler ?"})

    prompt = f"{user_message} (Réponds comme un expert en livres et littérature)"
    reponse = appeler_huggingface(prompt)

    # Nettoyer la réponse si besoin
    if "[/INST]" in reponse:
        reponse = reponse.split("[/INST]")[-1].strip()

    return jsonify({"reponse": reponse})
