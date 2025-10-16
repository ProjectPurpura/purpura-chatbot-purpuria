FROM python:3.11.2-slim

WORKDIR /code

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /code/
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY chatbot /code/chatbot
COPY common /code/common
COPY dto.py /code/
COPY main.py /code/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]