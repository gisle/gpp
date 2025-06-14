GPP
----

A command line client for OpenAI's GPT models.

## Installation

A prerequisite is that [uv](https://docs.astral.sh/uv/getting-started/installation/) is installed.

Set up the Python environment by running `uv venv`.  You should then see the
instructions to activate the Python environment for your shell.  Alternatively,
you can install a link to the `gpp` script:

```sh
ln -s $(uv run which gpp) ~/bin/gpp
```

Get an [OpenAI API token](https://platform.openai.com/account/api-keys) and make it available from the environment variable `OPENAI_API_KEY`, or alternatively
save it in the file `~/.gpp/openai-key.txt`.

If you have access to an Azure OpenAI endpoint, it can be configured by creating
the file `~/.gpp/azure-conf.json` and filling it with parameters in this format:

```json
{
  "azure_endpoint": "https://<your-name>.openai.azure.com/",
  "api_key": "<secret>"
}
```

You can also override `azure_deployment` from this configuration file. It can
be useful if you have deployments that do not match the model names of OpenAI, but
this has the side effect that the option `--model` then no longer has any effect.

## Usage

Normally, you would run `gpp` with your question as an argument. For example:

```sh
$ gpp What owl species have been observed in Norway\?
```

Here the backslash `\` before `?` is necessary to prevent the shell from trying to expand
filename that starts with "Norway". Alternatively, put the entire question between
quotes or run `gpp` without an argument so that it reads the question from `stdin`.
If you don't use a Unix shell, there will be other rules for how arguments
are evaluated and passed to programs like `gpp`.

If you want to continue the last conversation instead of starting a new one, give the option `--continue` (which can be abbreviated `-c`).
Alternatively, start the text with one or more periods, like this:

```sh
$ gpp ...Can you set up a table of the species\? Include wingspan and weight.
```

Special commands that are recognized are:

* `gpp list [<n> | all | files]`: This lists the last conversations you have had. Here `<n>` is the number of conversations to list, where `7` is the default value. The number printed at the beginning of each line is what you can use with `gpp recall` to view the whole conversation.  Reqesting a listing of `0` cause all conversations to be listed, which is the same as requesting it with `gpp list all`.

  The `gpp list files` variant prints all the absolute names of the JSON files that stores the conversations (newest first).  Can for instance be used to manipulate these with with other Unix tools. For instance a pipeline like `gpp list files | tail -n +50 | xargs echo rm` could be used to prune your history by limiting it to the last 50 conversations you had.

* `gpp recall [<n>]`: This prints out the nth last conversation you've had. The default value for `<n>` is 1, which is the last conversation.

## System prompt

The personality of `gpp` can be controlled by specifying your own system prompt with the option `--system`. Here you can either specify a full sentence or just the name of a file that you create under the `~/.gpp/system/` directory. You can also edit
the default behavior of gpp by editing directly in the file `~/.gpp/system/default`.

System prompt files support command interpolation. You can include shell
commands within your system prompt text using the syntax `$(command)`. When the
prompt is loaded, these commands will be executed in the shell, and their output
will be inserted into the prompt dynamically.  This feature allows you to create
dynamic and context-aware system prompts that can adapt based on the output of
shell commands.

For example, you can include the current date in your system prompt like this:

```
You're a helpful assistant.  Current time is $(date).
```

System files can also be prefixed with a JSON object which, for instance, can be used to override the default values for parameters
for the conversation. Here you can, for example, choose the model or temperature. For details on what can be controlled here, see
the API documentation linked below.

Run `gpp --help` to learn what other options you can use with the command.

## How to run inference locally

If you install [LM Studio](https://lmstudio.ai) then you can easily set up a local OpenAI-API server based on your LLM-model of choice.
To make `gpp` talk to the local server instead of OpenAI's official server you just set the `GPP_API` environment variable to `http://localhost:1234/v1/`.  When you want some questions to still be redirected to the official OpenAI server just pass in `--api openai` as option.

Another option for running local models is [Ollama](https://ollama.com) which
when installed will create the API service endpoint at
`http://localhost:11434/v1`.

If you need to provide an API key you can set the `GPP_API_KEY` environment variable.

## See also

https://platform.openai.com/docs/guides/gpt/chat-completions-api describes the API used, and https://github.com/openai/openai-python is the main Python library used to access this API.

https://llm.datasette.io is a similar tool written by Simon Willison.
