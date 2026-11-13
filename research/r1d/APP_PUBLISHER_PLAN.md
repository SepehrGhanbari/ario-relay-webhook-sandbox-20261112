# Ario R1d — fail-only GitHub App check producer scaffold

**LAB / HOLD. No GitHub App registered, no App key created, no check published, no ruleset changed.**

The user-authorized attempt to register a **new, private** App was stopped by GitHub's required 2FA/sudo-mode challenge on 2026-11-13. No authentication challenge was bypassed. This code is therefore a reviewable scaffold, not an installed GitHub check producer.

## Scope, invariants

- Target exclusively `SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a` PR **#9** (Draft R1b) or PR **#10** (R1c fake-green negative fixture); never `SepehrGhanbari/Ario` or any production branch.
- The generated check is always named `ario-r1d-lab-app-gate` and always `completed` / `failure`. This program *cannot* emit `success`, `neutral` or `skipped` and cannot approve a merge.
- App must be installed **only** on that single disposable repository, with `Checks: Read & write` and, only if GitHub's required-check source selector requires it, `Commit statuses: Read & write`. `Metadata: read` is implicit. No Administration, Workflows write, Contents write, Secrets, organization permissions or unnecessary account permissions.
- Private key is read only from a local pathname on a trusted workstation. Do not paste it into chat, GitHub issue/PR, Actions secrets of an untrusted workflow, this repository or the hosted browser automation. Do not commit a `.pem`, tokens or `.env` anywhere. Prefer operating-system protected storage and explicitly revoke the lab key after the exercise.
- Before any **live** use, operator must read and verify this exact source and target; this public branch is not an independently protected supply chain. Code is only isolated from PR #10, not independent from owner-operated infrastructure.
- Public REST readbacks check PR number, base and head SHAs (and origin repos), open state and mutable metadata at multiple points. They do not provide an *atomic* merge gate.
- For this pilot, no independent *test suite* has been defined; failure status is a safe negative control and **not proof that any code was tested**.

## Reproduce local tests (no credentials)

```bash
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

The tests mock App identity, installation scope and write tokens, and verify fail-closed responses. No network requests are made by the tests.

## Prepare a dry run (after reviewing the exact PR HEAD/base)

For PR #10, recorded SHA values at the time this scaffold was prepared:

```bash
python publisher.py --pr 10 \
  --head 0eec58824f969ba056e363d1c1f84dfe563b0964 \
  --base be7c16d964872f88ddb9029f2677c49a7cd745ba
```

The default is `DRY_RUN`, producing a JSON payload but **no Check Run**. An out-of-date SHA causes `HOLD`, not silent refreshing of an untrusted PR. This requires a network-capable trusted operator machine.

## Live failure-only publication (NOT YET ENABLED)

Registration + installation + owner-managed key storage must be completed before even attempting this command. Do not use real credentials in the sandbox repo or in chat.

```bash
python -m pip install PyJWT cryptography
# Set these environment variables in the trusted execution environment only.
# ARIO_R1D_APP_ID=<exact newly created LAB GitHub App numeric ID>
# ARIO_R1D_INSTALLATION_ID=<installation ID scoped to ONLY the disposable repo>
# ARIO_R1D_PRIVATE_KEY_PATH=<OS-protected local PEM file path>
# ARIO_R1D_TARGET_REPO=SepehrGhanbari/Ario-solo-rehearsal-20261111-r0a
python publisher.py --pr 10 \
  --head 0eec58824f969ba056e363d1c1f84dfe563b0964 \
  --base be7c16d964872f88ddb9029f2677c49a7cd745ba \
  --publish-failure
```

The program obtains an App JWT (short lifetime), checks `/app` and the installation identity/scope, requests an installation token limited to the single sandbox repository with `checks:write`, re-fetches the PR exact SHA, and publishes a **failure** Check Run. It does **not** print the private key, JWT or installation token. Even if it publishes, this result by itself is **not** trusted test execution or production merge authorization.

## Next actual GitHub enforcement experiment (requires App and explicit staging)

1. Register a new private lab App, satisfy GitHub's 2FA, install it on only the disposable rehearsal repository. Keep its key outside PR, Actions and chat.
2. Publish the first **fail-only** Check Run and verify `check_runs[].app.id` is the **new App ID**, not the GitHub Actions App `15368`.
3. Create a **separate disposable protected branch** and test a Ruleset that requires exact check name plus `integration_id` of the new App, with no bypass; do not replace the historical R0 ruleset or alter Ario `main`.
4. Run negative scenarios: PR workflow `exit 0` fake green from App 15368, `skipped`, `neutral`, missing App check, mismatched head/base, and removed/reopened review evidence; record each native GitHub response. Keep `R1d=HOLD` unless all required experiments pass.
5. A genuine positive control needs a protected independent evaluation service with immutable code, test execution and a separate credential custodian. It is **not supplied** by this scaffold. If a source-bound check is skipped/neutral but still satisfies GitHub rules, this is a new FAIL to resolve, not a success.

The current R0 FAIL and R1b/R1c limited observations remain unchanged. #133/#151 HOLD; permanent Ario signer/Trust NO_GO.