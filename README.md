# Homepage Opener

Enter a company’s homepage and get a three-line email opener for its founder. Each draft includes the homepage excerpt it used and a link to verify it.

## Run locally

Requires Python 3.10 or newer. Run `python app.py` and open [localhost:8000](http://127.0.0.1:8000). Paste a company homepage or click **Try an example** to use the built-in fictional homepage. The default workflow needs no account or API key.

## Enable the model

Install [Ollama](https://ollama.com/download), start it, and pull [Qwen2.5 1.5B](https://ollama.com/library/qwen2.5:1.5b) with `ollama pull qwen2.5:1.5b`. Set `OPENER_MODEL` to `qwen2.5:1.5b` before starting the app.

PowerShell:

```powershell
$env:OPENER_MODEL = "qwen2.5:1.5b"
python app.py
```

macOS / Linux:

```sh
OPENER_MODEL=qwen2.5:1.5b python3 app.py
```

The optional model uses the [local Ollama chat API](https://docs.ollama.com/api/chat) to choose an excerpt and question angle. The application renders those choices into three lines and switches to built-in rules if Ollama is unavailable or the response is invalid. The result shows which method ran.

## Scope

The fetcher reads one public HTML page and follows up to four redirects. It prefers visible text and can fall back to a public page description in the HTML metadata. The result identifies the meta tag when that happens. Sites that block automated requests or provide no product copy in the HTML may return an error. Drafts are in English and preserve source excerpts in their original wording.

Run the regression checks with `python -m unittest`.

## Deploy on Vercel

Import the repository in Vercel. The included configuration serves the frontend from `web/` and runs `/api/draft` as a Python function. The hosted version uses the built-in drafting rules. Follow the local setup above to try Ollama.

After deploying, open the deployment URL and click **Try an example**. Confirm that the app returns a three-line draft and shows the source excerpt.
