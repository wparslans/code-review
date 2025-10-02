import os
import json
import openai
from github import Github, Auth

# --- Setup ---
openai.api_key = os.getenv("OPENAI_API_KEY")
g = Github(auth=Auth.Token(os.getenv("GITHUB_TOKEN")))
repo = g.get_repo(os.getenv("GITHUB_REPOSITORY"))

# --- Get PR number ---
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

# --- PHPCS Comments as line reviews (per file) ---
if "files" in phpcs_report:
    for file_path, data in phpcs_report["files"].items():
        # Simple path conversion - take only the filename if path is complex
        if "/" in file_path:
            relative_path = file_path.split("/")[-1]  # Just the filename
        else:
            relative_path = file_path

        print(f"📁 Processing PHPCS issues for: {relative_path} (original: {file_path})")

        # Group messages by line number
        issues_by_line = {}
        for message in data.get("messages", []):
            line = message.get("line", 1) or 1
            issue_text = f"**PHPCS {message['type']}:** {message['message']} ({message['source']})"
            issues_by_line.setdefault(line, []).append(issue_text)

        # Post one comment per line, combining issues
        for line, issues in issues_by_line.items():
            try:
                comment_body = "\n".join(issues)
                pr.create_review_comment(
                    body=comment_body,
                    commit=pr.head.sha,
                    path=relative_path,
                    line=line
                )
                print(f"✅ Added PHPCS review comment for {relative_path} line {line} ({len(issues)} issues)")
            except Exception as e:
                print(f"❌ Could not add PHPCS review comment for {relative_path} line {line}: {e}")

# --- AI Review (per file) ---
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

        # Create a review instead of individual comments for AI
        try:
            review = pr.create_review(
                commit=pr.head.sha,
                body=f"## 🤖 AI Review for `{f.filename}`\n\n{comment}",
                event="COMMENT"
            )
            print(f"✅ Added AI review for {f.filename}")
        except Exception as e:
            print(f"❌ Could not add AI review for {f.filename}: {e}")

    except Exception as e:
        print(f"❌ AI Review failed for {f.filename}: {e}")
