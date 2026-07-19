# Groq LLM setup

The explanation provider uses Groq's OpenAI-compatible Chat Completions API.
API keys are read only from the process environment and must not be committed.

## Windows PowerShell

For the current terminal session:

```powershell
$env:GROQ_API_KEY = "your-new-key"
& 'C:\Users\T590\anaconda3\envs\devsim_env\python.exe' ai\integrated_visualization_app.py
```

In the GUI, choose `external_llm` under **Explanation Provider**. Choose `auto`
only when falling back to deterministic mock explanations is acceptable.

To persist the key, create a user environment variable in Windows Environment
Variables and restart the IDE. The Groq web console is used to create, revoke,
and restrict keys. The application selects its model locally with `LLM_MODEL`.

## Defaults and overrides

- API key variable: `GROQ_API_KEY`
- Model: `openai/gpt-oss-120b`
- Base URL: `https://api.groq.com/openai/v1`

For lower latency or a larger free-tier token allowance:

```powershell
$env:LLM_MODEL = "openai/gpt-oss-20b"
```

The application sends selected analyzer evidence and conclusions in JSON Object
Mode. Python remains responsible for evidence scoring and selection; the LLM is
responsible for ordering and wording the selected results.
