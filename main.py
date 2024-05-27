from fastapi import FastAPI

app = FastAPI()


@app.get("/hello")
async def hello(param: str = None):
    return {"message": "Hello World", "param": param.upper()}
