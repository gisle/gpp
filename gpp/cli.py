#!/usr/bin/env python

import os
import sys
import click
from openai import OpenAI, APIConnectionError, BadRequestError, NotFoundError

import json
import tomllib
import re
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

basedir = Path.home() / ".gpp"
basedir.mkdir(exist_ok=True)
(basedir / "chats").mkdir(exist_ok=True)
(basedir / "system").mkdir(exist_ok=True)

default_system = basedir / "system" / "default"
if not default_system.exists():
  default_system.write_text(
    "Du er en ekspert som er sikker i din sak og hjelper til med å forklare hvordan "
    "ting henger sammen. Fortrinnsvis ønsker du å svare kort og presist på norsk. "
    "Formatter svaret med Markdown."
  )

config_file = basedir / "config.toml"
if not config_file.exists():
  config_file.write_text("""model = "gpt-5-mini"
model_reasoning_effort = "medium"

model_provider = "openai"

[model_providers.openai]
#base_url = "https://api.openai.com/v1"
env_key = "OPENAI_API_KEY"
""")

config = tomllib.loads(config_file.read_text())

console = Console()

chat_params_default = {
  'model': config.get('model', 'gpt-5-mini'),
  'reasoning_effort': config.get('model_reasoning_effort', 'low'),
  #'max_tokens': 10*1024,
  #'temperature': 0.3,
  #'top_p': 1.0,
  #'frequency_penalty': 0,
  #'presence_penalty': 0,
}

def print_json(d):
  console.print_json(data=d)
  #print(json.dumps(d, ensure_ascii=False, indent=2))

def get_client():
  provider = config["model_providers"].get(config.get('model_provider', 'openai'), {})
  if provider.get('wire_api', 'chat') != 'chat':
      console.print("[red]Error:[/red] Only chat providers are supported")
      sys.exit(1)
  args = {}
  if 'bearer_token' in provider:
    args['api_key'] = provider['bearer_token']
  elif 'env_key' in provider:
    args['api_key'] = os.getenv(provider['env_key'])
  for k in ('base_url',):
    if k in provider:
      args[k] = provider[k]

  return OpenAI(**args)

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

def interpolate_commands(text: str) -> str:
  import subprocess
  import re
  # Find all $(...) patterns and replace with command output
  pattern = re.compile(r'\$\(([^)]+)\)')
  def repl(match):
    cmd = match.group(1)
    try:
      output = subprocess.check_output(cmd, shell=True, text=True)
      return output.strip()
    except Exception:
      return f"<error executing {cmd}>"
  return pattern.sub(repl, text)

def stream_response(response, chat, process_chunk, process_stop=None):
  answer = []
  answer_text = ""
  for chunk in response:
    chunk_data = chunk.model_dump(exclude_unset=True)
    chat['resp'].append(chunk_data)
    delta_text = ""
    if chunk.choices:
      if c := chunk.choices[0].delta.content:
        delta_text = c
        answer.append(c)
    answer_text = ''.join(answer)
    process_chunk(chunk_data, delta_text, answer_text)
  if process_stop:
    process_stop(answer_text)
  return answer_text

def format_api_status_error(error: BadRequestError | NotFoundError) -> list[str]:
  body = error.body if isinstance(error.body, dict) else {}
  payload = body.get('error') if isinstance(body.get('error'), dict) else body

  message = payload.get('message') if isinstance(payload.get('message'), str) else error.message
  lines = [f"[red]Error:[/red] {message}"]

  param = payload.get('param') if isinstance(payload.get('param'), str) else None
  code = payload.get('code') if isinstance(payload.get('code'), str) else None
  request_id = error.request_id

  details = []
  if param:
    details.append(f"param={param}")
  if code:
    details.append(f"code={code}")
  if request_id:
    details.append(f"request_id={request_id}")

  if details:
    lines.append(f"[dim]Details: {', '.join(details)}[/dim]")

  return lines

@click.command()
@click.argument('question', nargs=-1)
@click.option('--new/--continue', '-n/-c', default=True, help="Continue previous conversation or start a new one. The default is --new.")
@click.option('--system', '-s', default="default", help='Replace the default system persona')
@click.option('--model', help=f"What model to use which defaults to '{chat_params_default['model']}'")
@click.option('--effort', help=f"Override reasoning effort (default: '{chat_params_default['reasoning_effort']}').")
@click.option('-4', 'gpt_4', is_flag=True, help="Shortcut for --model=gpt-4.1")
@click.option('-5', 'gpt_5', is_flag=True, help="Shortcut for --model=gpt-5")
@click.option('--temperature', type=click.FloatRange(0, 3), help=f"How creative/random should generated text be.")
@click.option('--top-p', type=click.FloatRange(0, 1), help=f"Cut-off point for what tokens to consider in output.")
@click.option('--stream/--no-stream', default=True, show_default=True, help="Output tokens as they are generated, trade responsiveness for longer time until complete output")
@click.option('--json/--no-json', 'output_json', show_default=True, help="Output JSON API response as received for the curious")
@click.option('--raw/--no-raw', 'output_raw', default=False, show_default=True, help="Output assistant text as raw stdout (no markdown rendering)")
def main(question, new, system, model, effort, gpt_4, gpt_5, temperature, top_p, stream, output_json, output_raw):
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
    elif output_raw:
      for m in chat['messages']:
        print(f"[{m['role']}]")
        print(m['content'])
        print()
    else:
      icon = {
        'system': '🛂',
        'user': '👤',
        'assistant': '👽',
      }
      for m in chat['messages']:
        console.rule(icon[m['role']])
        console.print(Markdown(m['content']), style=("bold" if m['role'] == 'user' else None))
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
  if output_json and output_raw:
    console.print("[red]Error:[/red] --json and --raw are mutually exclusive")
    return

  if model is not None:       chat_params['model'] = model
  if effort is not None:      chat_params['reasoning_effort'] = effort
  if gpt_4:                   chat_params['model'] = 'gpt-4.1'
  if gpt_5:                   chat_params['model'] = 'gpt-5'
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
      sys_message = interpolate_commands(sys_message)
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
    client = get_client()
    response = client.chat.completions.create(
      messages=messages,
      stream=stream,
      stream_options={
        "include_obfuscation": False,
        "include_usage": True,
      } if stream else None,
      **chat_params
    )
  except (BadRequestError, NotFoundError) as e:
    for line in format_api_status_error(e):
      console.print(line)
    return
  except APIConnectionError as e:
    console.print(f"[red]Error:[/red] {e} Can't connect to {e.request.url}")
    return

  answer = ""

  if stream:
    if output_json:
      answer = stream_response(
        response,
        chat,
        process_chunk=lambda chunk_data, _delta_text, _answer: print_json(chunk_data),
      )
    elif output_raw:
      answer = stream_response(
        response,
        chat,
        process_chunk=lambda _chunk_data, delta_text, _answer: print(delta_text, end='', flush=True),
        process_stop=lambda _answer: print(),
      )
    else:
      with Live(Markdown(""), console=console, vertical_overflow="visible") as live:
        answer = stream_response(
          response,
          chat,
          process_chunk=lambda _chunk_data, _delta_text, answer_text: live.update(Markdown(answer_text), refresh=True),
          process_stop=lambda _answer: console.print(),
        )
  else:
    answer = response.choices[0].message.content
    chat['resp'].append(response.model_dump(exclude_unset=True))
    if output_json:
      print_json(response.model_dump())
    elif output_raw:
      print(answer)
    else:
      console.print(Markdown(answer))

  messages.append(
    {
      "role": "assistant",
      "content": answer
    }
  )

  # Save the chat
  write_chatfile(chatfile, chat)

if __name__ == '__main__':
    main()
