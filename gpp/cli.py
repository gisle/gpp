#!/usr/bin/env python

import os
import sys
import click
import openai
import json
from pathlib import Path

basedir = Path.home() / ".gpp"
basedir.mkdir(exist_ok=True)

openai.api_key = os.getenv("OPENAI_API_KEY") or (basedir / "openai-key.txt").read_text()[:-1]

@click.command()
@click.argument('question', nargs=-1)
def main(question):
  question = ' '.join(question)

  response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
      {
        "role": "system",
        "content": "Du er en ekspert som hjelper til med å forklare hvordan ting henger sammen. Fortrinnsvis ønsker du å svare kort og presist på norsk."
      },
      {
        "role": "user",
        "content": question,
      }
    ],
    temperature=1,
    max_tokens=1024,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0,
    stream=True,
  )

  for chunk in response:
    if d := chunk['choices'][0]['delta']:
       print(d['content'], end='', flush=True)

  print()


if __name__ == '__main__':
    main()