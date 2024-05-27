from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI()


@app.get("/hello")
async def hello(param: str = None):
    return {"message": "Hello World", "param": param.upper()}


class Hello(BaseModel):
    message: str
    param: str


@app.post("/write")
async def write(request: Request, hello: Hello):
    print(request.headers['token'])
    print(hello)
    return {"message": "Write", "param": f"Hello(mes={hello.message}, param={hello.param})"}
