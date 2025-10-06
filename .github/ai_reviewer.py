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

# --- Get existing comments to avoid duplicates ---
def get_existing_comments():
    """Get all existing review comments to check for duplicates"""
    existing_comments = {}
    try:
        reviews = pr.get_reviews()
        for review in reviews:
            comments = review.get_comments()
            for comment in comments:
                key = (comment.path, comment.position, comment.body.split('\n')[0])  # Use first line as identifier
                existing_comments[key] = True
    except Exception as e:
        print(f"⚠️ Could not fetch existing comments: {e}")
    return existing_comments

existing_comments = get_existing_comments()

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
                
                # Check if similar comment already exists
                first_issue = issues[0].split('\n')[0] if issues else ""
                comment_key = (relative_path, line, first_issue)
                
                if comment_key in existing_comments:
                    print(f"⏭️  Skipping duplicate comment for {relative_path} line {line}")
                    continue
                
                pr.create_review_comment(
                    body=comment_body,
                    commit=pr.head.sha,
                    path=relative_path,
                    line=line
                )
                print(f"✅ Added PHPCS review comment for {relative_path} line {line} ({len(issues)} issues)")
                
                # Add to existing comments to avoid duplicates in same run
                existing_comments[comment_key] = True
                
            except Exception as e:
                print(f"❌ Could not add PHPCS review comment for {relative_path} line {line}: {e}")

# --- AI Review (per file) ---
# Get existing AI reviews to avoid duplicates
existing_ai_reviews = {}
try:
    reviews = pr.get_reviews()
    for review in reviews:
        if review.body and "🤖 AI Review for" in review.body:
            # Extract filename from review body
            import re
            match = re.search(r"🤖 AI Review for `([^`]+)`", review.body)
            if match:
                filename = match.group(1)
                existing_ai_reviews[filename] = True
except Exception as e:
    print(f"⚠️ Could not fetch existing AI reviews: {e}")

for f in pr.get_files():
    # Skip if AI review already exists for this file
    if f.filename in existing_ai_reviews:
        print(f"⏭️  Skipping AI review for {f.filename} - already exists")
        continue
        
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
            
            # Mark as reviewed to avoid duplicates
            existing_ai_reviews[f.filename] = True
            
        except Exception as e:
            print(f"❌ Could not add AI review for {f.filename}: {e}")

    except Exception as e:
        print(f"❌ AI Review failed for {f.filename}: {e}")
