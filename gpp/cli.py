#!/usr/bin/env python

import os
import sys
import click
import openai
import json
from pathlib import Path
from datetime import datetime
from rich.console import Console

basedir = Path.home() / ".gpp"
basedir.mkdir(exist_ok=True)
(basedir / "chats").mkdir(exist_ok=True)

openai.api_key = os.getenv("OPENAI_API_KEY") or (basedir / "openai-key.txt").read_text()[:-1]

console = Console()

def print_json(d):
  console.print_json(data=d)
  #print(json.dumps(d, ensure_ascii=False, indent=2))

def get_chatfiles():
    return sorted(basedir.glob("chats/chat-*.json"), reverse=True)

@click.command()
@click.argument('question', nargs=-1)
@click.option('--new/--continue', '-n/-c', default=True, help="Continue previus conversation or start a new one. The default is --new.")
@click.option('--model', default='gpt-3.5-turbo', show_default=True)
@click.option('--temperature', default=0.8, show_default=True)
@click.option('--top-p', default=1.0, type=click.FloatRange(0, 1), show_default=True)
@click.option('--stream/--no-stream', default=True, show_default=True)
@click.option('--json/--no-json', 'output_json', show_default=True)
def main(question, new, model, temperature, top_p, stream, output_json):
  """
  The gpp command is an interface to OpenAI's conversation models.
  Just provide the questions you want to ask as argument(s) to the gpp command
  or pipe the question to the command without giving arguments.
  This is an assistant that prefers to use Norwegian language.

  To continue a conversation instead of starting a new one each time
  pass in the -c option (which can also be spelled --continue).

  The follow subcommands can be given as question to access the current
  chat history; "gpp list" and "gpp recall".
  The list command can take a the number of conversations to list.
  Without a number it just lists the latest few conversations.
  Use "gpp list all" to list all the conversations recorded.
  The recall command can take a the chat number from the list to recall that
  conversation.  Without a number it returns the last conversation.
  """
  if len(question) in (1, 2) and question[0] == "list":
    count = 0
    max = 7 if len(question) == 1 else (0 if question[1] == 'all' else int(question[1]))
    for f in get_chatfiles():
      count += 1
      dt = datetime.fromisoformat(f.stem[5:])
      m = json.loads(f.read_bytes())
      txt = m[1]['content']
      if len(txt) < console.width - 25:
        txt += ' ⇢ ' + m[2]['content']
      txt = txt.replace("\n", " ")
      if len(txt) > console.width - 22:
        txt = txt[:console.width - 25] + '...'
      console.print(f"{count:2d}) {str(dt)[:-3]} {txt}")
      if max and count >= max:
        break
    return

  if len(question) in (1,2) and question[0] == "recall":
    n = 1 if len(question) == 1 else int(question[1])
    f = get_chatfiles()[n-1]
    msgs = json.loads(f.read_bytes())
    if output_json:
      print_json(msgs)
    else:
      icon = {
        'system': '🛂',
        'user': '👤',
        'assistant': '👽',
      }
      for m in msgs[1:]:
        console.rule(icon[m['role']])
        console.print(m['content'])
    return

  if len(question) == 0:
    # read the question from stdin
    question = [sys.stdin.read()]

  # perform conversation
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
    chatfile = get_chatfiles()[0]
    messages = json.loads(chatfile.read_bytes())

  messages.append({
    "role": "user",
    "content": ' '.join(question),
  })

  response = openai.ChatCompletion.create(
    model=model,
    messages=messages,
    temperature=temperature,
    max_tokens=1024,
    top_p=top_p,
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
    answer.append(response['choices'][0]['message']['content'])
    if output_json:
      print_json(response)
    else:
      console.print(answer[-1])

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