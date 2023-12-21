FROM python:3.9.13

RUN apt-get update && apt-get install -y ffmpeg

ADD . ./bot
WORKDIR /bot

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

ENV CHARACTER_FILE_PATH=character.json
ENV WHITELIST_PATH=.whitelist
ENV CHAT_LOG_PATH=logs/chat.log
ENV INCIDENTS_LOG_PATH=logs/incidents.log

ENV OPENAI_LANGUAGE_MODEL=gpt-4-1106-preview
ENV TOKEN_LIMIT=2000

ENV TELEGRAM_SECRET=${TELEGRAM_SECRET}
ENV OPENAI_SECRET=${OPENAI_SECRET}

CMD ["python3", "bot.py"]
