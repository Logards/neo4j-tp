# run.py
from app import create_app

app = create_app()

if __name__ == '__main__':
    # host='0.0.0.0' permet d'accéder au serveur depuis l'extérieur du conteneur/machine
    # debug=True active le mode debug (rechargement auto, messages d'erreur détaillés) - NE PAS UTILISER EN PRODUCTION
    app.run(host='0.0.0.0', port=5000, debug=True)