from models import Settings
from fastapi import FastAPI, Request
from pydantic import BaseModel
from firebase import FirebaseApi

import random
import string

import os
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "localhost:9099"


# consts
LENGTH_ROOM_ID = 6

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
async def room_create(request: Request, settings: Settings):
    # 新しいルームIDの作成
    def gen_room_id() -> str:
        chars = [random.choice(string.ascii_uppercase + string.digits)
                 for _ in [None]*LENGTH_ROOM_ID]
        return "".join(chars)

    id_not_generated = True
    api: FirebaseApi = None
    while id_not_generated:
        room_id = gen_room_id()
        api = FirebaseApi(request.headers['token'], room_id)
        id_not_generated = api.check_if_room_exists()

    # 生成したルームIDでルームの初期設定を行う
    api.create_room(settings, request.headers['name'])

    return {"room_id": room_id}


@app.post("/room/{room_id}/join")
async def room_join(room_id, request: Request):
    api = FirebaseApi(request.headers['token'], room_id)
    result = api.join_room(request.headers['name'])

    return result
