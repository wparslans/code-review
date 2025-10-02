import os
import json
import openai
from github import Github, Auth

# --- Setup ---
openai.api_key = os.getenv("OPENAI_API_KEY")
g = Github(auth=Auth.Token(os.getenv("GITHUB_TOKEN")))
repo = g.get_repo(os.getenv("GITHUB_REPOSITORY"))

# --- Get PR number from ref ---
ref = os.getenv("GITHUB_REF", "")
pr_number = None
if "refs/pull/" in ref:
    pr_number = ref.split("/")[2]

if not pr_number:
    print("⚠️ No PR number found, skipping review.")
    exit(0)

pr = repo.get_pull(int(pr_number))

# --- Load PHPCS Report ---
phpcs_report = {}
if os.path.exists("phpcs.json"):
    with open("phpcs.json", "r") as f:
        phpcs_report = json.load(f)

phpcs_comments = []
if "files" in phpcs_report:
    for file, data in phpcs_report["files"].items():
        for m in data.get("messages", []):
            phpcs_comments.append(f"- **{file}:{m['line']}** {m['message']} ({m['source']})")

if phpcs_comments:
    try:
        pr.create_issue_comment("### 🔍 PHPCS Issues\n\n" + "\n".join(phpcs_comments))
    except Exception as e:
        print(f"❌ Could not add PHPCS issue comment: {e}")

# --- AI Review ---
for f in pr.get_files():
    diff = f.patch
    if not diff:
        continue

    prompt = f"""
    You are an Expert WordPress code reviewer.
    Review this code diff for:
    - WordPress Coding Standards (WPCS)
    - Security (sanitization, escaping, nonce, SQL injection, XSS, CSRF)
    - Good practices (hooks, OOP, internationalization, performance, function prefix with loginpress_)
    - Suggest improvements with examples

    Code diff:\n{diff}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert WordPress code reviewer."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )

        comment = response["choices"][0]["message"]["content"]

        try:
            pr.create_review_comment(
                body=f"🤖 **AI Review Suggestion**\n\n{comment}",
                commit_id=pr.head.sha,
                path=f.filename,
                line=1,  # fallback: top of file
                side="RIGHT"
            )
        except Exception as e:
            print(f"❌ Could not add AI inline comment: {e}")

    except Exception as e:
        print(f"❌ AI Review failed: {e}")
