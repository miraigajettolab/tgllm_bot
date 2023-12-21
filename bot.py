import os
import json
import logging
import subprocess
import openai
import datetime
import numpy as np
from telegram import Update
from telegram.ext import (
    filters,
    MessageHandler,
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

openai.api_key = os.getenv("OPENAI_SECRET")
TELEGRAM_SECRET = os.getenv("TELEGRAM_SECRET")

WHITELIST_PATH = os.getenv("WHITELIST_PATH")
CHARACTER_FILE_PATH = os.getenv("CHARACTER_FILE_PATH")
CHAT_LOG_PATH = os.getenv("CHAT_LOG_PATH")
INCIDENTS_LOG_PATH = os.getenv("INCIDENTS_LOG_PATH")

OPENAI_LANGUAGE_MODEL = os.getenv("OPENAI_LANGUAGE_MODEL")
TOKEN_LIMIT = int(os.getenv("TOKEN_LIMIT"))

with open(WHITELIST_PATH) as whitelist_file:
    accepted_user_ids = whitelist_file.read().splitlines()
    whitelist_file.close()

with open(CHARACTER_FILE_PATH, encoding="utf8") as character_file:
    character_data = json.load(character_file)
    default_responses = character_data["default_responses"]
    character_name = character_data["name"]
    system_prompt = character_data["prompt"]
    character_file.close()

context = []
costs = []


def get_depth():
    arr = np.flip(np.array(costs))
    return len(arr[arr.cumsum() <= TOKEN_LIMIT].tolist())


def prompt(chat_id, prompt, is_voice=False):
    user_prompt = {"role": "user", "content": prompt}
    context.append(user_prompt)
    depth = get_depth()

    result = openai.ChatCompletion.create(
        model=OPENAI_LANGUAGE_MODEL,
        messages=system_prompt
        + context[
            -depth * 2 :
        ],  # x2 because context stores quesion and answer separately
    )
    response = result["choices"][0]["message"]["content"]
    cost = result["usage"]["total_tokens"]

    history_costs = sum(costs[-depth:])
    current_cost = cost - history_costs
    costs.append(current_cost)
    context.append({"role": "assistant", "content": response})

    current_line = f"{chat_id}: {prompt}\n{character_name}: {response}\ncost: {cost}; current_cost: {current_cost}\n"
    log_to_file(CHAT_LOG_PATH, current_line)

    return response


def reset_context():
    context.clear()
    costs.clear()


def log_to_file(log_path, log_text):
    timestamp = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a+") as log_file:
        log_file.writelines(f"{timestamp} {log_text}")
        log_file.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=default_responses["welcome"],
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_context()
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=default_responses["history_reset"]
    )


async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) in accepted_user_ids:
        response = prompt(update.effective_chat.id, update.message.text)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
    else:
        log_to_file(
            INCIDENTS_LOG_PATH,
            f"Message from unauthorized user with id: {update.effective_chat.id}",
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=default_responses["unauthorized_user"],
        )


async def answer_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_chat.id) in accepted_user_ids:
        # get basic info about the voice note file and prepare it for downloading
        new_file = await context.bot.get_file(update.message.voice.file_id)
        os.makedirs("temp", exist_ok=True)
        await new_file.download_to_drive("temp/voice.ogg")
        subprocess.run(
            "ffmpeg -y -i temp/voice.ogg -ar 44100 -b:a 192k temp/voice.mp3",
            check=True,
            shell=True,
            stdout=subprocess.DEVNULL,
        )
        audio_file = open("temp/voice.mp3", "rb")
        transcript = openai.Audio.transcribe("whisper-1", audio_file)["text"]
        response = prompt(update.effective_chat.id, transcript, is_voice=True)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{default_responses['voice_transcription_prefix']}:\n{transcript}\n------\n\n{response}",
        )
    else:
        log_to_file(
            INCIDENTS_LOG_PATH,
            f"Voice message from unauthorized user with id: {update.effective_chat.id}",
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=default_responses["unauthorized_user"],
        )


if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_SECRET).build()

    start_handler = CommandHandler("start", start)
    reset_handler = CommandHandler("reset", reset)
    text_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), answer)
    voice_handler = MessageHandler(filters.VOICE, answer_voice)

    application.add_handler(start_handler)
    application.add_handler(reset_handler)
    application.add_handler(text_handler)
    application.add_handler(voice_handler)

    application.run_polling()
