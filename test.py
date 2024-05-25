# libs
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# サービスアカウントでログイン
cred = credentials.Certificate("firebase_secret.json")
firebase_admin.initialize_app(cred)

# データ追加
db = firestore.client()
query = db.collection('test')
query.add({'name': 'test'})
