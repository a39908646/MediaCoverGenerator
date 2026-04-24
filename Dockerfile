FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MCG_HOST=0.0.0.0
ENV MCG_PORT=38100

WORKDIR /app

COPY requirements.txt /app/
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 38100

CMD ["python", "-m", "mediacovergenerator"]
