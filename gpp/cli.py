#!/usr/bin/env python

import os
import sys
import click
import openai
import json
import re
from pathlib import Path
from datetime import datetime
from rich.console import Console

basedir = Path.home() / ".gpp"
basedir.mkdir(exist_ok=True)
(basedir / "chats").mkdir(exist_ok=True)
(basedir / "system").mkdir(exist_ok=True)

default_system = basedir / "system" / "default"
if not default_system.exists():
  default_system.write_text(
    "Du er en ekspert som er sikker i din sak og hjelper til med å forklare hvordan "
    "ting henger sammen. Fortrinnsvis ønsker du å svare kort og presist på norsk."
  )

openai.api_key = os.getenv("OPENAI_API_KEY") or (basedir / "openai-key.txt").read_text()[:-1]

console = Console()

def print_json(d):
  console.print_json(data=d)
  #print(json.dumps(d, ensure_ascii=False, indent=2))

def get_chatfiles() -> list[Path]:
    return sorted(basedir.glob("chats/chat-*.json"), reverse=True)

def read_chatfile(path : Path):
  d = json.loads(path.read_bytes())
  if isinstance(d, list):  # compatibility with old style chat files
    d = { 'model': 'gpt-3.5-turbo', 'messages': d }
  return d

def write_chatfile(path : Path | None, data):
  if not path:
    path = basedir / "chats" / ("chat-" + datetime.now().strftime('%Y%m%dT%H%M%S') + '.json')
  path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

@click.command()
@click.argument('question', nargs=-1)
@click.option('--new/--continue', '-n/-c', default=True, help="Continue previous conversation or start a new one. The default is --new.")
@click.option('--system', '-s', default="default", help='Replace the default system persona')
@click.option('--model', default='gpt-3.5-turbo', show_default=True)
@click.option('--temperature', default=0.8, show_default=True)
@click.option('--top-p', default=1.0, type=click.FloatRange(0, 1), show_default=True)
@click.option('--stream/--no-stream', default=True, show_default=True)
@click.option('--json/--no-json', 'output_json', show_default=True)
def main(question, new, system, model, temperature, top_p, stream, output_json):
  """
  The gpp command is an interface to OpenAI's conversation models.
  Just provide the questions you want to ask as argument(s) to the gpp command
  or pipe the question to the command without giving arguments.
  This is an assistant that prefers to use Norwegian language.

  To continue a conversation instead of starting a new one
  pass in the -c option (which can also be spelled --continue).
  You can also force continuation by prepending the question with
  a sequence of dots (one is enough).

  The follow subcommands can be given as question to access the current
  chat history; "gpp list" and "gpp recall".
  The list command can take a the number of conversations to list.
  Without a number it just lists the latest few conversations.
  Use "gpp list all" to list all the conversations recorded.
  The recall command can take a the chat number from the list to recall that
  conversation.  Without a number it returns the last conversation.
  """

  # implement the 'list' subcommand
  if len(question) in (1, 2) and question[0] == "list":
    count = 0
    max = 7 if len(question) == 1 else (0 if question[1] in ('all', 'files') else int(question[1]))
    last_date = None
    for f in get_chatfiles():
      if len(question) == 2 and question[1] == 'files':
        print(f)
        continue
      count += 1
      dt = datetime.fromisoformat(f.stem[5:])
      date = str(dt.date())
      if date == last_date:
        date = "[dim]" + date + "[/dim]"
      else:
        last_date = date
      time = str(dt.time())[:-3]

      m = read_chatfile(f)['messages']
      txt = m[1]['content']
      if len(txt) < console.width - 25:
        txt += ' ⇢ ' + m[2]['content']
      txt = txt.replace("\n", " ")
      if len(txt) > console.width - 22:
        txt = txt[:console.width - 25] + '...'
      console.print(f"{count:2d}. {date} {time} {txt}")
      if max and count >= max:
        break
    return

  # implement the 'recall' subcommand
  if len(question) in (1,2) and question[0] == "recall":
    n = 1 if len(question) == 1 else int(question[1])
    f = get_chatfiles()[n-1]
    chat = read_chatfile(f)
    if output_json:
      print_json(chat)
    else:
      icon = {
        'system': '🛂',
        'user': '👤',
        'assistant': '👽',
      }
      for m in chat['messages'][1:]:
        console.rule(icon[m['role']])
        console.print(m['content'], style=("bold" if m['role'] == 'user' else None))
        if m['role'] == 'assistant':
          console.print()
    return

  # preprocess the question
  if len(question) == 0:
    # read the question from stdin
    question = [sys.stdin.read()]
  elif m:= re.match(r'\.+\s*', question[0]):
    new = False
    question = list(question) # can't assign to tuple
    question[0] = question[0][m.end():] # drop matched dots

  # perform conversation
  if new:
    chatfile = None
    messages = []
    chat = {
      'model': model,
      'resp': [],
      'messages': messages,
    }
    if system != "none":
      if ' ' in system:
        sys_message = system
      else:
        sys_dir = basedir / "system"
        try:
          sys_message = (sys_dir / system).read_text()
        except FileNotFoundError:
          console.print(f"[red]Error: Unknown system {repr(system)}")
          console.print(f"Try one of these: {' '.join([repr(f.name) for f in sorted(sys_dir.iterdir())])}")
          return
      messages.append({ "role": "system", "content": sys_message })
  else:
    if system != "default":
      console.print("[red]Warning: Can't override system with continuation")
    chatfile = get_chatfiles()[0]
    chat = read_chatfile(chatfile)
    messages = chat['messages']

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
      if d := chunk['choices'][0]['delta']:
        answer.append(d['content'])
      if output_json:
        print_json(chunk)
      else:
        if d := chunk['choices'][0]['delta']:
          print(d['content'], end='', flush=True)
      chat['resp'].append(chunk)
    if not output_json:
      print()  # final newline
  else:
    answer.append(response['choices'][0]['message']['content'])
    chat['resp'].append(response)
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
  write_chatfile(chatfile, chat)

if __name__ == '__main__':
    main()