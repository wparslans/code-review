import os
import json
import openai
from github import Github

openai.api_key = os.getenv("OPENAI_API_KEY")
g = Github(os.getenv("GITHUB_TOKEN"))

repo = g.get_repo(os.getenv("GITHUB_REPOSITORY"))
pr_number = os.getenv("GITHUB_REF").split("/")[-1] if "pull" in os.getenv("GITHUB_REF", "") else None

if not pr_number:
    exit(0)

pr = repo.get_pull(int(pr_number))

# Load PHPCS results
phpcs_report = {}
if os.path.exists("phpcs.json"):
    with open("phpcs.json", "r") as f:
        phpcs_report = json.load(f)

# Add PHPCS inline comments
if "files" in phpcs_report:
    for file, data in phpcs_report["files"].items():
        for m in data.get("messages", []):
            try:
                pr.create_review_comment(
                    body=f"**WPCS:** {m['message']} ({m['source']})",
                    commit_id=pr.head.sha,
                    path=file,
                    line=m['line'],
                    side="RIGHT"
                )
            except Exception as e:
                print(f"Could not add PHPCS comment: {e}")

# AI Review for each changed file
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

    try:
        # Add AI comment to PR inline (top of file, safer fallback)
        pr.create_review_comment(
            body=f"**PR Review Bugs:**\n{comment}",
            commit_id=pr.head.sha,
            path=f.filename,
            line=f.changes if f.changes > 0 else 1,  # fallback line
            side="RIGHT"
        )
    except Exception as e:
        print(f"Unknown Issue: {e}")
