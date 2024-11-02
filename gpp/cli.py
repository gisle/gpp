#!/usr/bin/env python

import os
import sys
import click
from openai import OpenAI, AzureOpenAI, APIConnectionError

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

console = Console()

chat_params_default = {
  'model': 'gpt-4o',
  'max_tokens': 3072,
  'temperature': 0.3,
  'top_p': 1.0,
  'frequency_penalty': 0,
  'presence_penalty': 0,
}

def print_json(d):
  console.print_json(data=d)
  #print(json.dumps(d, ensure_ascii=False, indent=2))

def get_client(api, model):
  if api is None:
    if (basedir / "azure-conf.json").exists():
      api = 'azure'
    else:
      api = 'openai'

  if api == 'openai':
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY") or (basedir / "openai-key.txt").read_text()[:-1])

  if api == 'azure':
    with open(basedir / "azure-conf.json") as f:
      azure_conf = json.load(f)
      azure_conf.setdefault('azure_deployment', model.replace('.', ''))  # can't use dots in deployment name
      return AzureOpenAI(
        api_version="2023-12-01-preview",
        **azure_conf
      )

  return OpenAI(base_url=api, api_key='not-used')

def get_chatfiles() -> list[Path]:
    return sorted(basedir.glob("chats/chat-*.json"), reverse=True)

def read_chatfile(path : Path):
  d = json.loads(path.read_bytes())
  if isinstance(d, list):  # compatibility with old style chat files
    d = { 'params': {}, 'messages': d, 'resp': [] }
  elif 'params' not in d:
    d['params'] = { 'model': d['model'] }
  return d

def write_chatfile(path : Path | None, data):
  if not path:
    path = basedir / "chats" / ("chat-" + datetime.now().strftime('%Y%m%dT%H%M%S') + '.json')
  path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def set_dict_defaults(d, defaults):
  for k in defaults:
    if k not in d:
      d[k] = defaults[k]

@click.command()
@click.argument('question', nargs=-1)
@click.option('--new/--continue', '-n/-c', default=True, help="Continue previous conversation or start a new one. The default is --new.")
@click.option('--system', '-s', default="default", help='Replace the default system persona')
@click.option('--model', help=f"What model to use which defaults to '{chat_params_default['model']}'")
@click.option('-3', 'gpt_3', is_flag=True, help="Shortcut for --model=gpt-3.5-turbo")
@click.option('-4', 'gpt_4', is_flag=True, help="Shortcut for --model=gpt-4-turbo")
@click.option('--temperature', type=click.FloatRange(0, 3), help=f"How creative/random should generated text be. Default is {chat_params_default['temperature']}. Values above 1.5 tend to produce gibberish.")
@click.option('--top-p', type=click.FloatRange(0, 1), help=f"Cut-off point for what tokens to consider in output. Default is {chat_params_default['top_p']}.")
@click.option('--stream/--no-stream', default=True, show_default=True, help="Output tokens as they are generated, trade responsiveness for longer time until complete output")
@click.option('--json/--no-json', 'output_json', show_default=True, help="Output JSON API response as received for the curious")
@click.option('--api', envvar='GPP_API', help="Override the API server to use.  Either a URL or 'azure' or 'openai'. Default can be overridden by setting the GPP_API environment variable.")
def main(question, new, system, model, gpt_3, gpt_4, temperature, top_p, stream, output_json, api):
  """
  The gpp command is an interface to OpenAI's conversation models.
  Just provide the questions you want to ask as argument(s) to the gpp command
  or pipe the question to the command without giving arguments.
  This is an assistant that by default prefers to use Norwegian language.

  To continue a conversation instead of starting a new one
  pass in the -c option (which can also be spelled --continue).
  You can also force continuation by prepending the question with
  a sequence of dots (one is enough).

  The follow subcommands can be given as question to access the current
  chat history; "gpp list" and "gpp recall".
  The list command can takes the number of conversations to list as argument.
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
      for m in chat['messages']:
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

  chat_params = {}
  if model is not None:       chat_params['model'] = model
  if gpt_3:                   chat_params['model'] = 'gpt-3.5-turbo'
  if gpt_4:                   chat_params['model'] = 'gpt-4-turbo'
  if temperature is not None: chat_params['temperature'] = temperature
  if top_p is not None:       chat_params['top_p'] = top_p

  # perform conversation
  if new:
    chatfile = None
    messages = []
    chat = {
      'system': system,
      'params': chat_params,
      'messages': messages,
      'resp': [],
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
          console.print(f"Try one of these: {', '.join([repr(f.name) for f in sorted(sys_dir.iterdir())])} or 'none'")
          return
      if sys_message.startswith('{'):  # Extract JSON-prolog from system message
        sys_params, end = json.JSONDecoder().raw_decode(sys_message)
        sys_message = sys_message[end:].lstrip()
        set_dict_defaults(chat_params, sys_params)
      messages.append({ "role": "system", "content": sys_message })
  else:
    chatfile = get_chatfiles()[0]
    chat = read_chatfile(chatfile)
    if system != chat.get('system', 'default'):
      console.print("[red]Warning: Can't override system with continuation")
    set_dict_defaults(chat_params, chat['params'])
    messages = chat['messages']

  messages.append({
    "role": "user",
    "content": ' '.join(question),
  })

  set_dict_defaults(chat_params, chat_params_default)

  # console.print_json(data=chat); sys.exit(1)  # uncomment to debug param parsing

  try:
    client = get_client(api, chat_params['model'])
    response = client.chat.completions.create(
      messages=messages,
      stream=stream,
      **chat_params
    )
  except APIConnectionError as e:
    console.print(f"[red]Error:[/red] {e} Can't connect to {e.request.url}")
    return

  answer = []

  if stream:
    for chunk in response:
      chat['resp'].append(chunk.model_dump(exclude_unset=True))
      if chunk.choices:
        if c := chunk.choices[0].delta.content:
          answer.append(c)
          if not output_json:
            print(c, end='', flush=True)
      if output_json:
        print_json(chunk.model_dump(exclude_unset=True))
    if not output_json:
      print()  # final newline
  else:
    answer.append(response.choices[0].message.content)
    chat['resp'].append(response.model_dump(exclude_unset=True))
    if output_json:
      print_json(response.model_dump())
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
