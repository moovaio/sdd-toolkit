# Generic rule catalog

What to look for in a diff when the repo has no `ai-specs/sonar/rules.md` of its own. Rule keys
are SonarPHP's; most have a same-numbered twin in the other Sonar analyzers (`javascript:S1192`,
`python:S1192`…). A repo's own catalog, built from its history, always beats this list.

## What fails the gate

### Vulnerabilities — fail `new_security_rating`

- **Weak hashing** (`S4790`): `md5`/`sha1` (and equivalents) where the hash protects something.
  If it's not security-relevant (a checksum, a cache key), it still has to be marked as reviewed
  in Sonar.
- **Injection**: SQL, shell commands or paths built by concatenating request input.
- **Hard-coded secrets** (`S2068`, `S6418`): passwords, tokens, API keys as literals.
- **Unsafe deserialization**: `unserialize`, `pickle.loads`, `yaml.load` on input.
- **Command argument injection** (`pythonsecurity:S8705` and siblings): a CLI argument passed
  straight into a `subprocess`/`exec` argument list. Even without a shell, a value starting with
  `-` is read as an option (`git diff --output=<path>` writes a file). Sonar flags it on tooling
  scripts too — a helper that receives refs or paths from an agent is exactly its target. Fix:
  resolve the value to something the tool itself produced (e.g. `git rev-parse --verify
  --end-of-options <ref>^{commit}`) and pass only that.

  What the taint analysis accepts as a guard, learned the hard way: a `startswith("-")` and/or
  regex check followed by an exit, **written inline on the variable that reaches the command**.
  It does not see validation done inside an argparse `type=` function, it keeps tracing through a
  `subprocess` call's output, and a guard skipped on some path (`if x is not None and …`) counts
  as no guard on that path — assign the safe literal there instead. Even then it can keep finding
  one more path. Once the value is provably sanitized, stop restructuring and have someone mark
  the issue **Safe** in SonarCloud with the justification: that is what the transition is for.

### Security hotspots — fail `new_security_hotspots_reviewed` until reviewed

Code that *might* be a risk and needs a human to mark it safe in Sonar: regexes vulnerable to
backtracking (`S5852`), weak pseudo-random numbers for anything security-related (`S2245`),
permissive CORS, cookies without `Secure`/`HttpOnly`, disabled TLS verification, file permissions
like `0777`. A hotspot isn't a defect, but a new unreviewed one fails the gate: say it will need
reviewing.

### Bugs — fail `new_reliability_rating`

Rare in practice. Look for: loose comparisons where type matters, conditions that are always
true or false, unreachable code after `return`, identical branches in an `if`/`else`.

## Code smells — informational

A single new smell barely moves the maintainability rating (the A threshold is a 5% debt ratio
on new code). Report them, grouped, but don't present them as gate risks.

| Rule | What | Usual fix |
|---|---|---|
| `S1192` | Same string literal repeated in a file | A constant. Counts per file. The effective threshold is higher than "3 times" — don't flag by raw count; reserve it for clearly repeated payload or config literals |
| `S3776` | Cognitive complexity > 15 | Extract. Fires even if the signature is unchanged, as soon as new lines push the method over 15 — estimate before and after |
| `S1172` | Unused function parameter | If an interface or callback signature imposes it, don't delete it — mark it accepted |
| `S1142` | More than 3 `return`s | Usually chained guard clauses; decide case by case |
| `S112` | Throwing a generic exception | The domain's own exception class |
| `S3011` | Accessibility bypass via reflection | In tests it's usually deliberate |
| `S107` | More than 7 parameters | Often asks for a DTO |
| `S138` | Method over 150 lines | Extract |
| `S1448` | Class with too many methods | Report; refactoring rarely fits the PR |
| `S1481` | Unused local variable | Trivial |
| `S3358` | Nested ternary | An `if` or an intermediate variable |
| `S1488` | Assign to a temporary and return it immediately | Return the expression |
| `S1135` | `TODO` left in code | Mention it; fine if there's a ticket |

## Duplication

Measure it with `scripts/duplication.py`, not by eye. Common sources:

- **Near-identical generated or boilerplate files** (seeders, fixtures, migrations, config per
  environment): adding or touching one can score 70–90% on its own.
- **CI pipelines with one stage per environment** — Sonar analyzes some pipeline languages
  (a `Jenkinsfile` is Groovy).
- **New tests that copy a sibling test's setup** — a repeated setup block easily passes 95
  tokens. A data provider or a shared helper fixes it.
