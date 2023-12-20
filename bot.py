import os
import io
import json
import logging
import subprocess
import base64
import requests
import openai
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
ACCEPTED_USERS = [os.getenv("USER_CHAT_ID"), os.getenv("ADMIN_CHAT_ID")]
CHARACTER_NAME = os.getenv("CHARACTER_NAME")

with open(f"persona/{CHARACTER_NAME}.json", encoding="utf8") as persona_file:
    PERSONA = json.load(persona_file)
    CHARACTER = PERSONA["character"]
    persona_file.close()

context = []
costs = []
TOKEN_LIMIT = 2000


def get_depth():
    arr = np.flip(np.array(costs))
    return len(arr[arr.cumsum() <= TOKEN_LIMIT].tolist())


def prompt(chatId, prompt, isVoice=False):
    user_prompt = {"role": "user", "content": prompt}
    context.append(user_prompt)
    depth = get_depth()

    result = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=CHARACTER
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

    current_line = f"{chatId}: {prompt}\n{CHARACTER_NAME}: {response}; cost: {cost}; current_cost: {current_cost}\n"
    print(current_line)
    with open(f"log.txt", "a") as log_file:
        log_file.writelines(current_line)
        log_file.close()

    return response


def reset_context():
    context.clear()
    costs.clear()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hi, I'm a virtual assistant, how can I help you?",
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_context()
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Chat history was reset"
    )


async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) in ACCEPTED_USERS:
        response = prompt(update.effective_chat.id, update.message.text)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
    else:
        print("STRANGER!", update.effective_chat.id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="I'm not talking to strangers"
        )


async def answer_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_chat.id) in ACCEPTED_USERS:
        # get basic info about the voice note file and prepare it for downloading
        new_file = await context.bot.get_file(update.message.voice.file_id)
        await new_file.download_to_drive("temp/voice.ogg")
        subprocess.run(
            "ffmpeg -y -i temp/voice.ogg -ar 44100 -b:a 192k temp/voice.mp3",
            check=True,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        audio_file = open("temp/voice.mp3", "rb")
        transcript = openai.Audio.transcribe("whisper-1", audio_file)["text"]
        response = prompt(update.effective_chat.id, transcript, isVoice=True)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"You said:\n{transcript}\n------\n\n{response}",
        )
    else:
        print("STRANGER_VOICE!", update.effective_chat.id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Who is it?"
        )


if __name__ == "__main__":
    application = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

    start_handler = CommandHandler("start", start)
    reset_handler = CommandHandler("reset", reset)
    text_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), answer)
    voice_handler = MessageHandler(filters.VOICE, answer_voice)

    application.add_handler(start_handler)
    application.add_handler(reset_handler)
    application.add_handler(text_handler)
    application.add_handler(voice_handler)

    application.run_polling()
