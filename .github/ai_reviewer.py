import os
import json
import openai
from github import Github

# --- GitHub context ---
openai.api_key = os.getenv("OPENAI_API_KEY")
g = Github(os.getenv("GITHUB_TOKEN"))

with open(os.getenv("GITHUB_EVENT_PATH")) as f:
    event = json.load(f)

repo = g.get_repo(os.getenv("GITHUB_REPOSITORY"))
pr_number = event["pull_request"]["number"]
pr = repo.get_pull(pr_number)

# --- Load PHPCS results ---
phpcs_comments = []
if os.path.exists("phpcs.json"):
    with open("phpcs.json", "r") as f:
        phpcs_report = json.load(f)

    for file, data in phpcs_report.get("files", {}).items():
        for m in data.get("messages", []):
            phpcs_comments.append(f"- `{file}:{m['line']}` → {m['message']} _(Rule: {m['source']})_")

if phpcs_comments:
    pr.create_issue_comment("### 🔍 PHPCS Issues\n\n" + "\n".join(phpcs_comments))

# --- AI Review for each changed file ---
for f in pr.get_files():
    diff = f.patch
    if not diff:
        continue

    prompt = f"""
    You are an Expert WordPress code reviewer.
    Review this code diff for:
    - WordPress Coding Standards (WPCS)
    - Security (sanitization, escaping, nonce, SQL injection, XSS, CSRF)
    - Good practices (hooks, OOP, internationalization, performance checks, prefixes with loginpress_ in functions)

    Code diff:\n{diff}
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert WordPress code reviewer."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=400
    )

    comment = response["choices"][0]["message"]["content"]
    pr.create_issue_comment(f"### 🤖 AI Review for `{f.filename}`\n\n{comment}")
