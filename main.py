from fastapi import FastAPI, Request
from pydantic import BaseModel
from firebase import FirebaseApi

import os
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "localhost:9099"

app = FastAPI()


@app.post("/test")
async def test(request: Request):
    api = FirebaseApi(request.headers['token'], "AB12C3")
    print("is_member: ", api.is_member())
    print("role: ", api.get_role())


@app.post("/reset")
async def reset(request: Request):
    api = FirebaseApi(request.headers['token'], "AB12C3")
    api.reset_firestore()


@app.post("/room/create")
async def room_create(request: Request):
    print(request.body)
    return {"room_id": "1AB23C"}
