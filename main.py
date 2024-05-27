from fastapi import FastAPI, Request
from pydantic import BaseModel
from firebase import FirebaseApi

import os
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "localhost:9099"

app = FastAPI()


@app.get("/hello")
async def hello(param: str = None):
    return {"message": "Hello World", "param": param.upper()}


class Hello(BaseModel):
    message: str
    param: str


@app.post("/write")
async def write(request: Request, hello: Hello):
    api = FirebaseApi(request.headers['token'])
    print(api.uid)
    print(hello)
    return {"message": "Write", "param": f"Hello(mes={hello.message}, param={hello.param})"}


@app.post("/test")
async def test(request: Request):
    api = FirebaseApi(request.headers['token'], "AB12C3")
    print(api.is_member())


@app.post("/reset")
async def reset(request: Request):
    api = FirebaseApi(request.headers['token'], "AB12C3")
    api.reset_firestore()
