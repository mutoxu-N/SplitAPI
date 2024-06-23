from models import Settings, User
from fastapi import FastAPI, Request, Body, status
from pydantic import BaseModel
from firebase import FirebaseApi
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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


@app.post("/reset")
async def reset(request: Request):
    api = FirebaseApi(request.headers['token'], "AB12C3")
    api.reset_firestore()


@app.post("/room/create")
async def room_create(request: Request, settings: Settings = Body(embed=True)):
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


@app.post("/room/{room_id}/vote")
async def vote(room_id, request: Request, vote_for: str, accepted: bool):
    # TODO: Androidアプリ側の実装をしてからデバッグする
    api = FirebaseApi(request.headers['token'], room_id)
    result = api.vote(vote_for, accepted)
    return result


@app.post("/room/{room_id}/accept")
async def accept(room_id, request: Request, accept_for: str, accepted: bool):
    # TODO: Androidアプリ側の実装をしてからデバッグする
    api = FirebaseApi(request.headers['token'], room_id)
    result = api.accept(accept_for, accepted)
    return {"succeed": result}


@app.post("/room/{room_id}/create_guest")
async def create_guest(room_id, request: Request, user: User):
    api = FirebaseApi(request.headers['token'], room_id)
    result = api.create_guest(user)
    return {"succeed": result}


@app.exception_handler(RequestValidationError)
async def handler(request: Request, exc: RequestValidationError):
    print(exc)
    print(await request.json())
    return JSONResponse(content={}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
