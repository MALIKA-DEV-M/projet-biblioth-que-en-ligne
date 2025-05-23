# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify
import json
import os
import requests
import webbrowser

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

# === CONFIGURATION ===
GOOGLE_BOOKS_API_KEY = "AIzaSyBl03kApQIJq24ktCdQ8R1Aj_JSiO7mDKs"
HUGGINGFACE_TOKEN = "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"

# === GOOGLE BOOKS ===
def rechercher_livre_google(termes):
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {
        'q': termes,
        'key': GOOGLE_BOOKS_API_KEY,
        'maxResults': 3,
        'printType': 'books',
        'langRestrict': 'fr'
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        results = []
        if 'items' in data:
            for item in data['items']:
                info = item['volumeInfo']
                results.append({
                    'titre': info.get('title', 'Titre inconnu'),
                    'auteurs': ", ".join(info.get('authors', ['Auteur inconnu'])),
                    'description': info.get('description', 'Pas de description disponible.'),
                    'image': info.get('imageLinks', {}).get('thumbnail', None)
                })
        return results
    return []

# === OPEN LIBRARY ===
def rechercher_livre_openlibrary(termes):
    url = "https://openlibrary.org/search.json"
    params = {"q": termes, "language": "fre", "limit": 3}
    response = requests.get(url, params=params)
    livres = []
    if response.status_code == 200:
        data = response.json()
        for doc in data.get('docs', []):
            livres.append({
                'titre': doc.get('title', 'Titre inconnu'),
                'auteurs': ", ".join(doc.get('author_name', ['Auteur inconnu'])),
                'description': "Description non disponible via Open Library.",
                'image': f"https://covers.openlibrary.org/b/olid/{doc.get('cover_edition_key', '')}-M.jpg"
                          if doc.get('cover_edition_key') else None
            })
    return livres

# === COMBINE LES DEUX SOURCES ===
def chercher_dans_les_deux(termes):
    resultats = rechercher_livre_google(termes)
    if len(resultats) < 3:
        autres = rechercher_livre_openlibrary(termes)
        resultats.extend(autres)
    return resultats

# === HUGGING FACE (LLM) ===
def appeler_huggingface(prompt):
    url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
    headers = {
        "Authorization": HUGGINGFACE_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": f"[INST] {prompt} [/INST]",
        "parameters": {
            "max_new_tokens": 300,
            "temperature": 0.7
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            text = response.json()[0]['generated_text']
            return text.split("[/INST]")[-1].strip()
        else:
            return f"Erreur Hugging Face : {response.status_code}"
    except Exception as e:
        return f"Erreur Hugging Face : {str(e)}"

# === AMÉLIORATION DU PROMPT ===
def ameliorer_prompt(prompt_utilisateur):
    url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
    headers = {
        "Authorization": HUGGINGFACE_TOKEN,
        "Content-Type": "application/json"
    }

    prompt_systeme = f"""
Tu es un expert en littérature.

L'utilisateur cherche des recommandations de livres avec les critères suivants :
"{prompt_utilisateur}"

Tu dois transformer cette demande en une requête **optimisée et ciblée** pour une recherche littéraire. La requête reformulée doit inclure clairement :
- Le **genre** (ex: roman fantastique, policier…)
- Le **cadre géographique** (ex: Moyen-Orient, Égypte…)
- L’**époque** (ex: années 30, époque victorienne…)
- Le **type de personnage** (ex: jeune sorcier, femme détective…)
- La **caractéristique de l’auteur·e** si précisée (ex: écrit par une femme)

Règle d’or : tous les critères doivent être respectés dans la reformulation. Si une information est vague ou manquante, **ne l'invente pas**.

Donne uniquement la phrase reformulée. Ne propose pas d'essai, de livre documentaire, de magazine ou d'article. Seulement des **romans**.

Si aucun roman exact ne correspond à tous les critères, dis : "Aucune correspondance fiable trouvée."
    """

    payload = {
        "inputs": f"[INST] {prompt_systeme} [/INST]",
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.4
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            texte = response.json()[0]['generated_text']
            return texte.split("[/INST]")[-1].strip()
        else:
            return prompt_utilisateur
    except Exception:
        return prompt_utilisateur

# === ROUTES PRINCIPALES ===
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/livres')
def livres():
    with open('static/livres.json', 'r', encoding='utf-8-sig') as f:
        livres_data = json.load(f)
    return render_template('livres.html', livres=livres_data)

@app.route('/recommandation')
def recommandation():
    genre = request.args.get('genre')
    with open('static/livres.json', 'r', encoding='utf-8-sig') as f:
        livres_data = json.load(f)
    livres_recommandes = [livre for livre in livres_data if livre['genre'] == genre]
    return render_template('livres.html', livres=livres_recommandes)

# === ROUTE DE CHAT ===
dernier_prompt = None

@app.route('/chat', methods=['POST'])
def chat():
    global dernier_prompt
    user_message = request.json.get("message", "").strip().lower()

    if not user_message:
        return jsonify({"reponse": "Je n'ai pas compris. Peux-tu reformuler ?"})

    if user_message in ["reset", "nouvelle question", "nouveau sujet"]:
        dernier_prompt = None
        return jsonify({"reponse": "🧠 Mémoire effacée. Pose une nouvelle question."})

    message_complet = f"{dernier_prompt}. {user_message}" if dernier_prompt else user_message
    dernier_prompt = user_message

    prompt_ameliore = ameliorer_prompt(message_complet)
    livres = chercher_dans_les_deux(prompt_ameliore)

    # 🧹 Filtrage des résultats vagues ou hors sujet
    mots_cles = ["roman", "sorcier", "magie", "fantastique", "école"]
    livres = [livre for livre in livres if any(mot in livre['description'].lower() for mot in mots_cles)]

    if livres:
        reponse = f"<em>Recherche basée sur le prompt amélioré : <strong>{prompt_ameliore}</strong></em><br><br>"
        for livre in livres:
            reponse += f"<strong>{livre['titre']}</strong> par {livre['auteurs']}<br>"
            reponse += f"{livre['description']}<br>"
            if livre['image']:
                reponse += f"<img src='{livre['image']}' alt='Couverture'><br><br>"
    else:
        reponse = f"Aucun résultat trouvé pour : <strong>{prompt_ameliore}</strong>"

    return jsonify({
        "reponse": reponse,
        "prompt_ameliore": prompt_ameliore
    })

# === ROUTE POUR IA LITTÉRAIRE ===
@app.route('/ia', methods=['POST'])
def ia():
    question = request.json.get("message", "")
    if not question:
        return jsonify({"reponse": "Je n'ai pas compris la question."})

    prompt_ameliore = ameliorer_prompt(question)
    reponse = appeler_huggingface(prompt_ameliore)

    return jsonify({
        "reponse": reponse,
        "prompt_ameliore": prompt_ameliore
    })

# === RECHERCHE PERSONNALISÉE ===
@app.route('/find')
def find():
    nom_livre = request.args.get('nomlivre')
    auteur = request.args.get('auteur')
    genre = request.args.get('genre')
    edition = request.args.get('edition')

    termes = " ".join(filter(None, [nom_livre, auteur, genre, edition]))
    if not termes:
        return "Aucune donnée saisie", 400

    livres = rechercher_livre_google(termes)
    return render_template('livres.html', livres=livres)

# === LANCEMENT SERVEUR ===
if __name__ == '__main__':
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True)

