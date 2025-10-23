FROM python:3.11-slim as builder

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /code/
RUN pip install --no-cache-dir --upgrade --prefix=/install -r requirements.txt

FROM python:3.11-slim

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

COPY --from=builder /install /usr/local


COPY purpuria /code/purpuria
COPY common /code/common
COPY dto.py main.py /code/
COPY infoRedis.py /code/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]