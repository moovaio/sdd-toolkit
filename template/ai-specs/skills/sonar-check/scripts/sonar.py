#!/usr/bin/env python3
"""
Read-only queries against SonarQube Cloud for the current repo.

    sonar.py gate <pr>       quality gate conditions and their status
    sonar.py issues <pr>     issues on new code, with rule, file and line
    sonar.py hotspots <pr>   security hotspots of the PR
    sonar.py prs             analyzed PRs and their verdict
    sonar.py history [--last N] [--json]
                             what the gate failed on and which rules fired over
                             the last N analyzed PRs (default 60) -- the evidence
                             a repo's rule catalog and calibration are built from
    sonar.py whoami          the organization and project key in use

The organization and project key resolve, first match wins, from:
  --org / --project
  $SONAR_ORGANIZATION / $SONAR_PROJECT_KEY
  sonar-project.properties (sonar.organization / sonar.projectKey)
  the `origin` remote: SonarCloud's default for a GitHub-imported project is
  organization=<owner> and projectKey=<owner>_<repo>.

The token comes from $SONAR_TOKEN or ~/.config/sonar/token. An *organization
token* reaches the gate, issues and PR list, but measures/*, duplications/* and
hotspots/* answer "Project doesn't exist" or 404 -- which is why duplication is
measured locally by duplication.py instead.
"""
import argparse
import base64
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

HOST = "https://sonarcloud.io/api"
TOKEN_FILE = "~/.config/sonar/token"


def token():
    env = os.environ.get("SONAR_TOKEN")
    if env:
        return env.strip()
    path = pathlib.Path(os.path.expanduser(TOKEN_FILE))
    if path.is_file():
        return path.read_text().strip()
    sys.exit(f"Missing token: export SONAR_TOKEN or write it to {TOKEN_FILE}")


def from_properties():
    path = pathlib.Path("sonar-project.properties")
    if not path.is_file():
        return {}
    props = {}
    for line in path.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            props[key.strip()] = value.strip()
    return {
        "org": props.get("sonar.organization"),
        "project": props.get("sonar.projectKey"),
    }


def from_remote():
    url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    # git@github.com:owner/repo.git | https://github.com/owner/repo(.git)
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?$", url)
    if not match:
        return {}
    owner, repo = match.groups()
    return {"org": owner, "project": f"{owner}_{repo}"}


def resolve(args):
    sources = [
        {"org": args.org, "project": args.project},
        {
            "org": os.environ.get("SONAR_ORGANIZATION"),
            "project": os.environ.get("SONAR_PROJECT_KEY"),
        },
        from_properties(),
        from_remote(),
    ]
    found = {}
    for key in ("org", "project"):
        found[key] = next((s[key] for s in sources if s.get(key)), None)
        if not found[key]:
            sys.exit(f"Could not resolve the Sonar {key}: pass --{key}.")
    return found["org"], found["project"]


def call(endpoint):
    auth = base64.b64encode(f"{token()}:".encode()).decode()
    req = urllib.request.Request(
        f"{HOST}/{endpoint}", headers={"Authorization": f"Basic {auth}"}
    )
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as exc:
        return {"errors": [{"msg": f"HTTP {exc.code}"}]}
    except OSError as exc:
        return {"errors": [{"msg": str(exc)}]}


def bail(data):
    if "errors" in data:
        print("  error: " + "; ".join(e.get("msg", "?") for e in data["errors"]))
        return True
    return False


def gate(org, project, pr):
    data = call(f"qualitygates/project_status?projectKey={project}&pullRequest={pr}")
    if bail(data):
        return 1
    status = data["projectStatus"]
    print(f"Quality Gate: {status['status']}")
    for cond in status.get("conditions", []):
        flag = "OK  " if cond["status"] == "OK" else "FAIL"
        metric = cond["metricKey"]
        actual = cond.get("actualValue")
        limit = f"{cond.get('comparator')} {cond.get('errorThreshold')}"
        print(f"  [{flag}] {metric:<34} actual={actual:<8} threshold {limit}")
    return 0 if status["status"] == "OK" else 1


def issues(org, project, pr):
    data = call(
        f"issues/search?organization={org}&componentKeys={project}"
        f"&pullRequest={pr}&resolved=false&ps=500"
    )
    if bail(data):
        return 1
    print(f"  {data.get('total', 0)} issues on new code")
    for issue in data.get("issues", []):
        where = issue["component"].split(":", 1)[-1]
        line = issue.get("line", "-")
        print(
            f"  {issue['rule']:<16} {issue.get('type', ''):<12} "
            f"{issue.get('severity', ''):<9} {where}:{line}"
        )
        print(f"      {issue.get('message', '')}")
    return 0


def hotspots(org, project, pr):
    data = call(f"hotspots/search?projectKey={project}&pullRequest={pr}&ps=100")
    if data.get("errors", [{}])[0].get("msg") == "HTTP 404":
        print("  The organization token cannot reach hotspots/search (404). The condition's")
        print("  status still shows in `sonar.py gate`; listing them needs a user token with")
        print("  browse permission on the project.")
        return 1
    if bail(data):
        return 1
    found = data.get("hotspots", [])
    print(f"  {len(found)} security hotspots")
    for spot in found:
        where = spot.get("component", "").split(":")[-1]
        print(
            f"  {spot.get('ruleKey', ''):<22} {spot.get('status', '')} "
            f"{where}:{spot.get('line', '-')}"
        )
        print(f"      {spot.get('message', '')}")
    return 0


def prs(org, project):
    data = call(f"project_pull_requests/list?project={project}")
    if bail(data):
        return 1
    for pull in data.get("pullRequests", []):
        verdict = pull.get("status", {}).get("qualityGateStatus", "?")
        print(
            f"  PR {pull['key']:<6} {verdict:<6} "
            f"{pull.get('analysisDate', '')[:10]}  {pull.get('title', '')[:60]}"
        )
    return 0


def history(org, project, last, as_json):
    data = call(f"project_pull_requests/list?project={project}")
    if bail(data):
        return 1
    pulls = sorted(
        data.get("pullRequests", []),
        key=lambda p: p.get("analysisDate", ""),
        reverse=True,
    )[:last]

    failed_on, rules, per_pr = {}, {}, []
    for pull in pulls:
        key = pull["key"]
        status = call(
            f"qualitygates/project_status?projectKey={project}&pullRequest={key}"
        ).get("projectStatus", {})
        conditions = {
            c["metricKey"]: c for c in status.get("conditions", [])
        }
        for metric, cond in conditions.items():
            if cond.get("status") == "ERROR":
                failed_on[metric] = failed_on.get(metric, 0) + 1
        found = call(
            f"issues/search?organization={org}&componentKeys={project}"
            f"&pullRequest={key}&resolved=false&ps=500"
        ).get("issues", [])
        for issue in found:
            path = issue["component"].split(":", 1)[-1]
            entry = rules.setdefault(
                issue["rule"],
                {"type": issue.get("type"), "severity": issue.get("severity"),
                 "count": 0, "in_tests": 0, "example": issue.get("message", "")},
            )
            entry["count"] += 1
            if re.search(r"(^|/)(tests?|__tests__|spec)/|[._-](test|spec)\.", path):
                entry["in_tests"] += 1
        density = conditions.get("new_duplicated_lines_density", {})
        per_pr.append({
            "pr": key,
            "gate": status.get("status"),
            "duplication": density.get("actualValue"),
            "issues": len(found),
            "base": pull.get("target"),
        })

    result = {
        "project": project,
        "prs": len(pulls),
        "gate_failures": sum(1 for p in per_pr if p["gate"] == "ERROR"),
        "failed_on": dict(sorted(failed_on.items(), key=lambda kv: -kv[1])),
        "rules": dict(sorted(rules.items(), key=lambda kv: -kv[1]["count"])),
        "per_pr": per_pr,
    }
    if as_json:
        print(json.dumps(result, indent=1))
        return 0

    print(f"{result['prs']} analyzed PRs, gate failed {result['gate_failures']} times")
    for metric, count in result["failed_on"].items():
        print(f"  failed on {metric:<34} {count}")
    print(f"\n{sum(r['count'] for r in rules.values())} issues on new code, by rule:")
    for rule, entry in result["rules"].items():
        print(
            f"  {rule:<16} {entry['type'] or '':<14} {entry['severity'] or '':<9} "
            f"{entry['count']:>3}  ({entry['in_tests']} in tests)  {entry['example'][:60]}"
        )
    print("\nPer PR (duplication is the real new_duplicated_lines_density):")
    for pull in per_pr:
        print(
            f"  PR {pull['pr']:<6} {pull['gate'] or '?':<6} "
            f"dup={pull['duplication'] or '-':<6} issues={pull['issues']}"
        )
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("command", choices=["gate", "issues", "hotspots", "prs", "history", "whoami"])
    ap.add_argument("pr", nargs="?")
    ap.add_argument("--org")
    ap.add_argument("--project")
    ap.add_argument("--last", type=int, default=60)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    org, project = resolve(args)
    if args.command == "whoami":
        print(f"organization={org} project={project}")
        return 0
    if args.command == "prs":
        return prs(org, project)
    if args.command == "history":
        return history(org, project, args.last, args.json)
    if not args.pr:
        ap.error(f"{args.command} needs a PR number")
    return {"gate": gate, "issues": issues, "hotspots": hotspots}[args.command](
        org, project, args.pr
    )


if __name__ == "__main__":
    sys.exit(main())
