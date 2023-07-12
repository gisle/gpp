#!/usr/bin/env python

import os
import sys
import click
import openai
import json
from pathlib import Path
from datetime import datetime

basedir = Path.home() / ".gpp"
basedir.mkdir(exist_ok=True)
(basedir / "chats").mkdir(exist_ok=True)

openai.api_key = os.getenv("OPENAI_API_KEY") or (basedir / "openai-key.txt").read_text()[:-1]

def print_json(d):
  print(json.dumps(d, ensure_ascii=False, indent=2))

@click.command()
@click.argument('question', nargs=-1, required=True)
@click.option('--new/--continue', '-n/-c', default=True)
@click.option('--model', default='gpt-3.5-turbo', show_default=True)
@click.option('--stream/--no-stream', default=True)
@click.option('--json/--no-json', 'output_json')
def main(question, new, model, stream, output_json):
  if new:
    chatfile = None
    messages = [
      {
        "role": "system",
        "content": "Du er en ekspert som hjelper til med å forklare hvordan ting henger sammen. "
                  "Fortrinnsvis ønsker du å svare kort og presist på norsk."
      },
    ]
  else:
    chatfile = sorted(basedir.glob("chats/chat-*.json"), reverse=True)[0]
    messages = json.loads(chatfile.read_bytes())

  messages.append({
    "role": "user",
    "content": ' '.join(question),
  })

  response = openai.ChatCompletion.create(
    model=model,
    messages=messages,
    temperature=1,
    max_tokens=1024,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0,
    stream=stream,
  )

  answer = []

  if stream:
    for chunk in response:
      if output_json:
        print_json(chunk)
      else:
        if d := chunk['choices'][0]['delta']:
          answer.append(d['content'])
          print(d['content'], end='', flush=True)
    if not output_json:
      print()  # final newline
  else:
    if output_json:
      print_json(response)
    else:
      answer.append(response['choices'][0]['message']['content'])
      print(answer[-1])

  messages.append(
    {
      "role": "assistant",
      "content": ''.join(answer)
    }
  )

  # Save the chat
  if not chatfile:
    chatfile = basedir / "chats" / ("chat-" + datetime.now().strftime('%Y%m%dT%H%M%S') + '.json')
  chatfile.write_text(json.dumps(messages, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()