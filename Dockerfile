FROM python:3.11

COPY . /src
WORKDIR /src
RUN pip install --no-cache-dir --upgrade -r /src/requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "11512"]
