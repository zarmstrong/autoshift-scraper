import argparse
import json
from datetime import datetime, timezone
from os import path

from github import Github
from github.GithubException import UnknownObjectException

SHIFTCODESJSONPATH = "data/shiftcodes.json"


def upload_shiftfile(filepath, user, repo_name, token, commit_msg=None):
    """Upload or update shiftcodes.json in the specified GitHub repo (main branch)."""
    if not (user and repo_name and token):
        print("GitHub credentials incomplete; skipping upload.")
        return False
    commit_msg = commit_msg or "Update shiftcodes.json (marked expired) via mark_expired.py"
    with open(filepath, "rb") as f:
        content_bytes = f.read()
    content_str = content_bytes.decode("utf-8")
    try:
        g = Github(token)
        repo = g.get_repo(f"{user}/{repo_name}")
        try:
            contents = repo.get_contents("shiftcodes.json", ref="main")
            repo.update_file(contents.path, commit_msg, content_str, contents.sha, branch="main")
            print("Updated shiftcodes.json in repo.")
        except UnknownObjectException:
            # file doesn't exist; create it
            repo.create_file("shiftcodes.json", commit_msg, content_str, branch="main")
            print("Created shiftcodes.json in repo.")
        return True
    except Exception as e:
        print("GitHub upload failed:", e)
        return False


def load_file(fn):
    if not path.exists(fn):
        raise SystemExit(f"File not found: {fn}")
    with open(fn, "r", encoding="utf-8") as f:
        return json.load(f)


def save_file(fn, data):
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def mark_expired(codes_to_mark, expires_override=None, filepath=SHIFTCODESJSONPATH):
    data = load_file(filepath)
    if not data or not isinstance(data, list) or "codes" not in data[0]:
        raise SystemExit("Unexpected shiftcodes.json format")
    entries = data[0]["codes"]
    found = 0
    not_found = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for target in codes_to_mark:
        t = target.strip().upper()
        matched = False
        for e in entries:
            code_val = (e.get("code") or "").strip().upper()
            if code_val == t:
                matched = True
                if expires_override:
                    e["expires"] = expires_override
                else:
                    e["expires"] = now_iso
                e["expired"] = True
                found += 1
        if not matched:
            not_found.append(t)
    save_file(filepath, data)
    return found, not_found


def main():
    p = argparse.ArgumentParser(description="Mark one or more SHiFT codes as expired in data/shiftcodes.json")
    p.add_argument("codes", nargs="+", help="SHiFT code(s) to mark expired (exact match). Can pass multiple codes.")
    p.add_argument("--expires", default=None, help="Optional ISO datetime to set in the 'expires' field (defaults to now UTC)")
    p.add_argument("--file", default=SHIFTCODESJSONPATH, help="Path to shiftcodes.json (default: data/shiftcodes.json)")
    # optional GitHub push parameters
    p.add_argument("--user", default=None, help="GitHub username or org that owns the repo (optional, to push file)")
    p.add_argument("--repo", default=None, help="GitHub repository name (optional, to push file)")
    p.add_argument("--token", default=None, help="GitHub token with contents:write permission (optional, to push file)")
    args = p.parse_args()

    found, not_found = mark_expired(args.codes, expires_override=args.expires, filepath=args.file)
    print(f"Marked expired: {found}")
    if not_found:
        print("Not found:", ", ".join(not_found))

    # If GitHub credentials provided, upload the updated file
    if args.user and args.repo and args.token:
        ok = upload_shiftfile(args.file, args.user, args.repo, args.token,
                              commit_msg=f"Marked expired via mark_expired.py: {', '.join(args.codes)}")
        if ok:
            print("Uploaded updated shiftcodes.json to GitHub.")
        else:
            print("Upload attempt failed.")


if __name__ == "__main__":
    main()
