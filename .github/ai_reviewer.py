import os
import json
import openai
import re
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
        for message in data.get("messages", []):
            try:
                # Create review comment on specific line
                pr.create_review_comment(
                    body=f"**PHPCS {message['type']}:** {message['message']} ({message['source']})",
                    commit=pr.head.sha,
                    path=file_path,
                    line=message['line']
                )
                print(f"✅ Added PHPCS review comment for {file_path} line {message['line']}")
            except Exception as e:
                print(f"❌ Could not add PHPCS review comment for {file_path} line {message['line']}: {e}")

# --- AI Review with line-specific comments ---
for f in pr.get_files():
    diff = f.patch
    if not diff:
        continue

    prompt = f"""
    Analyze this code diff and identify specific issues. For each issue found:
    1. Mention the exact line number
    2. Describe the problem
    3. Suggest a fix
    
    Focus on:
    - WordPress Coding Standards violations
    - Security issues (SQL injection, XSS, CSRF, etc.)
    - Bad practices (naming, structure, etc.)
    
    Format your response with line numbers clearly marked.
    
    Code diff:\n{diff}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert WordPress code reviewer. Provide line-specific feedback with exact line numbers."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=600
        )

        ai_feedback = response["choices"][0]["message"]["content"]
        
        # Try to parse line numbers from AI response and create line comments
        lines = ai_feedback.split('\n')
        for line in lines:
            # Look for patterns like "Line 12:", "line 10:", etc.
            line_match = re.search(r'(?:line|Line)\s+(\d+)[:\-]', line)
            if line_match:
                line_number = int(line_match.group(1))
                try:
                    # Create review comment on the specific line
                    pr.create_review_comment(
                        body=f"**AI Review:** {line.strip()}",
                        commit=pr.head.sha,
                        path=f.filename,
                        line=line_number
                    )
                    print(f"✅ Added AI review comment for {f.filename} line {line_number}")
                except Exception as e:
                    print(f"❌ Could not add AI review comment for {f.filename} line {line_number}: {e}")

    except Exception as e:
        print(f"❌ AI Review failed for {f.filename}: {e}")