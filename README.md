## Put your telegram and openai tokens in the .secret file, place it in the project root

```
TELEGRAM_SECRET=...
OPENAI_SECRET=...
```

## Put allowed telegram ids in the .whitelist file, with each id on a new line

## Edit other configs directly in the Dockerfile

## Put your system promt in the character.json file with the following structure

```
{
  "name": "Assistant",
  "default_responses": {
    "welcome": "Hi, I'm a virtual assistant, how can I help you?",
    "history_reset": "Chat history was reset",
    "unauthorized_user": "You're not authorized to use this bot",
    "voice_transcription_prefix": "You said"
  },
  "prompt": [
    {
      "role": "system",
      "content": "Your system prompt goes here"
    }
  ]
}
```

## (Re)build&Run with upgrade.sh
