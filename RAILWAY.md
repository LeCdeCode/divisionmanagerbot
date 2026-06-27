# Railway deployment

## Variables d'environnement à définir dans Railway

- `BOT_TOKEN`: token de ton bot Discord
- `DATA_DIR=/app/data`: répertoire de stockage des JSON et du transcript
- `KEEP_ALIVE=false` (optionnel)

## Persistance

Le bot écrit ses données dans `data/` (ou `DATA_DIR` si défini).
Pour que la persistance survive aux redeploys et restarts, crée un volume Railway monté sur `/app/data`.

## Start command

Si tu n'utilises pas Docker, utilise :

```bash
python main.py
```

Si Railway détecte le `Dockerfile`, il utilisera automatiquement le conteneur ci-joint.
