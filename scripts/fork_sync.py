"""Nightly fork update (fork change 11), run by Task Scheduler with Hermes's venv python.

Merges NousResearch's main into the fork in a scratch copy. Sonnet reads the new commit titles
against the user's changes; if it flags anything, or git hits conflicts, one session on the user's
own model applies the rules at the top of FORK.md. The result is pushed to the fork, then
`hermes update --yes` installs it. A failure writes update-hold.json and installs the fork as it was.

    fork_sync.py                         start a run through Task Scheduler (outside Hermes, so the
                                         install cannot cut it off), for ad-hoc runs too
    fork_sync.py --from-task             the run itself (the task's command line)
    fork_sync.py --dry-run FORK UPSTREAM  replay two commits with today's FORK.md; push and install nothing

Every run ends with a report session in the user's session list (--report, in a fresh process so it
runs on the newly installed code). The task runs the script in a PowerShell window that stays open
(-NoExit); the window shows only live progress (step start times and the install's output), since
the results are in the report.
"""
import argparse
import asyncio
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from hermes_cli.config import load_config_readonly
from hermes_cli.gateway_chat import run_gateway_chat
from hermes_constants import get_hermes_home

HOME = Path(get_hermes_home())
STATE = HOME / "fork-sync"
WORK = STATE / "work"
PROMPTS = Path(__file__).with_name("fork_sync")
UPSTREAM = "https://github.com/NousResearch/hermes-agent.git"
TRIAGE = ("openrouter", "meta/muse-spark-1.3-contributor")
FALLBACK = ("openrouter", "deepseek/deepseek-v4.1-flash-1017")
REVIEW = ("openrouter", "meta/muse-spark-1.3-contributor")
DESKTOP = REPO / "apps" / "desktop" / "release"
TASK = "Hermes Auto Update"


class Hold(Exception):
    pass


RECORD = []  # what this run did, for the report session


def record(text):
    RECORD.append(text.strip())


def say(step):
    """One progress line in the task's window; results belong in the report, not here."""
    print(f"[{datetime.now():%H:%M:%S}] {step}", flush=True)


def git(*args, cwd=REPO, check=True):
    r = subprocess.run(["git", "-C", str(cwd), *args], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise Hold(f"git {' '.join(args[:2])} failed: {(r.stderr or r.stdout).strip()[-600:]}")
    return r


def setting(path):
    node = load_config_readonly()
    for key in path.split("."):
        node = node.get(key) if isinstance(node, dict) else None
    return node or None


class _Result:
    """The emitter interface Hermes's chat view reports a finished turn to."""
    result: dict = {}
    def bind_session(self, _): pass
    def on_text_delta(self, _): pass
    def on_tool_progress(self, *a, **k): pass
    def emit_result(self, result, session_id="", exit_code=0):
        self.result = dict(result or {})
        return exit_code


def _openrouter_key():
    """Safe mode reads no profile .env, so the key is passed with the session."""
    env = HOME / ".env"
    for line in env.read_text(encoding="utf-8-sig").splitlines() if env.exists() else []:
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'") or None
    return None


def _session(prompt, provider, model, tools, source):
    out = _Result()
    args = argparse.Namespace(oneshot=prompt, provider=provider, model=model, toolsets=",".join(tools),
                              max_turns=150, yolo=True, safe_mode=True, source=source,
                              in_dir=str(WORK if WORK.exists() else STATE),
                              quiet=True, reasoning=setting("agent.reasoning_effort"),
                              api_key=_openrouter_key() if provider == "openrouter" else None)
    try:
        asyncio.run(run_gateway_chat(args, emitter=out))
    except Exception as exc:
        out.result = {"failed": True, "error": str(exc)}
    r = out.result
    with open(STATE / "spend.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "model": model,
                            **{k: r.get(k) for k in ("input_tokens", "output_tokens", "cache_read_tokens",
                                                     "cache_write_tokens", "estimated_cost_usd", "error")}}) + "\n")
    return r


def ask(prompt, provider, model, tools, source="tool"):
    """One unattended session through the running gateway; its cost goes to spend.jsonl. Retries both
    models with growing waits; if none replies, raises Hold with the real errors (the update then
    installs the fork as it was and reports the hold)."""
    # OpenRouter and the backend (paused or restarting during an update) both fail transiently, so
    # keep trying both models with growing waits (~10 minutes in all) before giving up.
    errors = []
    for wait in (0, 15, 30, 60, 120, 240):
        if wait:
            say(f"No reply yet; trying again in {wait} seconds.")
            time.sleep(wait)
        for prov, mod in dict.fromkeys([(provider, model), FALLBACK]):
            r = _session(prompt, prov, mod, tools, source)
            reply = str(r.get("final_response") or "").strip()
            if not r.get("failed") and reply:
                return reply, r.get("estimated_cost_usd") or 0
            errors.append(f"{mod}: {r.get('error') or 'empty reply'}")
    raise Hold(f"No model replied after {len(errors)} attempts over about 10 minutes. "
               f"Last errors: {'; '.join(errors[-2:])}")


def your_changes():
    """FORK.md, the user's plugins, and the built-in skills he has edited."""
    plugins = [d.name for root in ("plugins", "desktop-plugins") for d in (HOME / root).glob("*") if d.is_dir()]
    from tools import skills_sync as s
    manifest, bundled = s._read_manifest(), WORK / "skills"
    skills = [src.relative_to(bundled).as_posix() for name, src in s._discover_bundled_skills(bundled)
              if manifest.get(name) and s._compute_relative_dest(src, bundled).is_dir()
              and not s._matches_origin_hash(s._compute_relative_dest(src, bundled), manifest[name])]
    return ((WORK / "FORK.md").read_text(encoding="utf-8") + "\n\n## The user's plugins\n\n" + "\n".join(plugins)
            + "\n\n## Built-in skills the user has edited (under skills/)\n\n" + "\n".join(skills))


def merge(fork, upstream, fork_md=None):
    """Merge and review in WORK. Returns the note for the user ('' when nothing needed review)."""
    # Git marks its object files read-only; Windows refuses to delete them until that is cleared.
    say("Merging NousResearch's changes in a scratch copy...")
    if WORK.exists():
        shutil.rmtree(WORK, onerror=lambda f, p, _: (os.chmod(p, stat.S_IWRITE), f(p)))
    git("clone", "-q", "--shared", "--no-checkout", str(REPO), str(WORK), cwd=STATE)
    for args in (("remote", "remove", "origin"), ("config", "user.name", "GarishGumdrop"),
                 ("config", "user.email", "github.gumdrop@proton.me"), ("checkout", "-q", "--detach", fork)):
        git(*args, cwd=WORK)
    if fork_md:  # replay: today's FORK.md rules on an old fork commit
        shutil.copy(fork_md, WORK / "FORK.md")
        git("commit", "-qam", "replay: today's FORK.md", "--no-verify", cwd=WORK)
        fork = git("rev-parse", "HEAD", cwd=WORK).stdout.strip()
    base = git("merge-base", fork, upstream, cwd=WORK).stdout.strip()
    log = git("log", "--first-parent", "--format=%h%x1f%s%x1f%b%x1e", f"{base}..{upstream}", cwd=WORK).stdout
    titles = []
    for rec in filter(None, (r.strip() for r in log.split("\x1e"))):
        sha, subject, body = (rec.split("\x1f") + ["", ""])[:3]
        if subject.startswith("Merge pull request") and body.strip():
            subject = body.strip().splitlines()[0]  # the PR's title
        titles.append(f"{sha} {subject}")
    record(f"{len(titles)} new NousResearch commit(s).")
    titles = "\n".join(titles)
    clean = git("merge", "--no-ff", "--no-edit", "-m", "Merge NousResearch main", upstream, cwd=WORK, check=False).returncode == 0
    clashes = git("diff", "--name-only", "--diff-filter=U", cwd=WORK).stdout.strip()
    record(f"Git conflicts: {clashes or 'none'}.")

    say(f"Triage running ({TRIAGE[1]})...")
    flags, cost = ask((PROMPTS / "triage.md").read_text(encoding="utf-8").format(
        changes=your_changes(), commits=titles), *TRIAGE, tools=[])
    record(f"Triage ({TRIAGE[1]}) flagged:\n{flags}")
    if flags.strip("` \njson") == "[]" and clean:
        record("Nothing flagged and no conflicts, so no review was needed.")
        return "", cost
    say(f"Review running ({REVIEW[1]}); this can take a while...")
    note, review_cost = ask((PROMPTS / "review.md").read_text(encoding="utf-8").format(
        fork=fork, upstream=upstream, flags=flags, clashes=clashes or "none",
        python=sys.executable), *REVIEW, tools=["file", "terminal"],
        source="cli")  # "cli" shows the review in the user's session list; "tool" is hidden
    cost += review_cost
    record(f"Review ({REVIEW[1]}) reply:\n{note}")
    if (WORK / ".git" / "MERGE_HEAD").exists() or git("merge-base", "--is-ancestor", upstream, "HEAD", cwd=WORK, check=False).returncode:
        raise Hold(note or "The review left the merge unfinished.")
    return note, cost


REPORT_PROMPT = """Below is the record of one run of the user's Hermes update. Write him the report of this run. He is not
a programmer: plain English, short, no preamble, in this order:

1. What came in from NousResearch (how many commits), or that nothing new came in.
2. What the triage flagged, one line each, or that nothing was flagged.
3. What the review decided for each flagged item, keeping its substance, with anything waiting for his
   decision stated plainly.
4. Anything that failed or was held, and what that means for him.
5. Whether the install succeeded.
6. The model cost.

# Record

"""


def report(path):
    """The report session: the cheap model turns this run's record into the user's report."""
    prompt = REPORT_PROMPT + Path(path).read_text(encoding="utf-8")
    for _ in range(10):  # the install restarts the gateway; wait for it to come back
        try:
            ask(prompt, *TRIAGE, tools=[], source="cli")
            return
        except Hold:
            time.sleep(30)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", nargs=2, metavar=("FORK", "UPSTREAM"))
    p.add_argument("--from-task", action="store_true")
    p.add_argument("--report")
    a = p.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    if a.dry_run:
        note, cost = merge(*a.dry_run, fork_md=REPO / "FORK.md")
        print(note or "(nothing needed review)", f"\n\nModel cost: ${cost:.2f}")
        return
    if a.report:
        return report(a.report)
    if not a.from_task:
        subprocess.run(["schtasks.exe", "/run", "/tn", TASK], check=True)
        print("Started the update through Task Scheduler. Its report will appear as a session when it finishes.")
        return
    sys.stdout.reconfigure(errors="replace")
    say("Hermes nightly update started.")
    record(f"Run started {datetime.now():%Y-%m-%d %H:%M}.")
    hold = HOME / "update-hold.json"
    cost = 0
    try:
        say("Fetching your fork and NousResearch's main...")
        git("fetch", "-q", "origin", "+refs/heads/main:refs/fork-sync/origin")
        git("fetch", "-q", "--no-tags", UPSTREAM, "+refs/heads/main:refs/fork-sync/upstream")
        git("fetch", "-q", "--no-tags", UPSTREAM, "+refs/tags/v*:refs/tags/v*", check=False)
        fork, upstream = (git("rev-parse", r).stdout.strip() for r in ("refs/fork-sync/origin", "refs/fork-sync/upstream"))
        if not git("merge-base", "--is-ancestor", upstream, fork, check=False).returncode:
            record("Nothing new from NousResearch since the last merge.")
        else:
            note, cost = merge(fork, upstream)
            say("Checking that the merged result loads...")
            r = subprocess.run([sys.executable, "-c", "import run_agent, hermes_cli.main, gateway.run"],
                               check=False, cwd=WORK, capture_output=True, text=True)
            if r.returncode:
                raise Hold(f"{note}\n\nThe merged result does not load:\n{r.stderr[-1500:]}")
            say("Pushing the merged result to your fork...")
            git("fetch", "-q", str(WORK), "+HEAD:refs/fork-sync/result")
            git("push", "-q", "origin", "refs/fork-sync/result:refs/heads/main")
            record("The merged result was pushed to the fork.")
            if note:
                notes = json.loads((HOME / "update-notes.json").read_text(encoding="utf-8-sig")) \
                    if (HOME / "update-notes.json").exists() else {"notes": []}
                notes["notes"].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                       "text": f"Tonight's update reviewed NousResearch's changes. {note}\n\nModel cost: ${cost:.2f}"})
                (HOME / "update-notes.json").write_text(json.dumps(notes, indent=1), encoding="utf-8")
        hold.unlink(missing_ok=True)
    except Exception as exc:
        record("HELD: NousResearch's changes were not merged; Hermes is updated to the fork as it was. "
               f"Reason:\n{str(exc)[-3000:]}")
        hold.write_text(json.dumps({"since": datetime.now().isoformat(timespec="seconds"),
                                    "reason": "NousResearch's changes were not merged into your fork tonight; "
                                              "Hermes was updated to your fork as it was.",
                                    "files": [], "detail": str(exc)[-3000:]}, indent=2), encoding="utf-8")
    record(f"Model cost of the merge and review: ${cost:.2f} (estimate at API prices).")
    import psutil
    open_app = next((p.info["exe"] for p in psutil.process_iter(["name", "exe"])
                     if p.info["name"] == "Hermes.exe" and str(DESKTOP).lower() in (p.info["exe"] or "").lower()), None)
    say("Installing (hermes update); its output follows.")
    # Hermes's own launcher (REPO/.hermes/bin) runs the managed Python; REPO/venv is a stale
    # Python 3.11 leftover that cannot run current Hermes (requires 3.14).
    launcher = REPO / ".hermes" / "bin" / ("hermes.CMD" if os.name == "nt" else "hermes")
    hermes = str(launcher if launcher.exists() else REPO / "venv" / "Scripts" / "hermes.exe")
    say(f"Using {hermes}")
    proc = subprocess.Popen([hermes, "update", "--yes"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    lines = []
    for line in proc.stdout:
        print("    " + line.rstrip(), flush=True)
        lines.append(line.rstrip())
    returncode = proc.wait()
    tail = "\n".join("\n".join(lines).strip().splitlines()[-25:])
    outcome = "succeeded" if returncode == 0 else f"FAILED with exit code {returncode}"
    record(f"Install (hermes update) {outcome}. Last lines of its output:\n{tail}")
    if open_app:
        subprocess.Popen(["explorer.exe", open_app])
    path = STATE / "last-run.txt"
    path.write_text("\n\n".join(RECORD), encoding="utf-8")
    say("Writing the report...")
    subprocess.run([sys.executable, str(Path(__file__)), "--report", str(path)], check=False)
    say("Finished. The report is in your session list. You can close this window.")


if __name__ == "__main__":
    main()
