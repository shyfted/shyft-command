# Shyft Command Pre-Migration Audit

Created: 2026-08-03 22:34:00 AEST
Stabilisation updated: 2026-08-03 22:52 AEST

## 1. Executive Summary

This repository is the current CMS and emerging Shyft Command codebase. It is an active Git repository on `main`, tracking `origin/main`, with no local-only commits at the time of audit.

The working tree is intentionally dirty. The tracked changes and untracked files are concentrated in two workstreams:

- ShyftTab / Android / Petey power-management investigation.
- Hanshow integration discovery and reference material.

Stabilisation has now preserved the legitimate ShyftTab/Android work in Git, moved Hanshow discovery material out of Command, hardened ignore rules, and preserved the local runtime database. The repository is ready for the later controlled relocation once final validation is accepted.

## 2. Repository Identity

| Item | Value |
| --- | --- |
| Absolute path | `/Users/katmeintjes/Shyfted/products/shyft-command` |
| Current branch | `main` |
| Upstream | `origin/main` |
| Remote | `origin` -> `https://github.com/shyfted/shyfted_cms` |
| Latest commit | `5a9187d Rebrand customer-facing CMS as Shyft Command` |
| Ahead/behind | `0 behind, 0 ahead` |
| Local-only commits | None detected by upstream comparison |
| Repository size | `220M` |
| Nested Git repositories | None detected beyond `./.git` |
| Dirty status at initial audit | 3 tracked modified files, 44 untracked files, ignored runtime/generated material present |
| Stabilisation commits | `5c8ece5 Harden Command ignore and runtime boundaries`; `18939eb Add ShyftTab presence-based LCD power control` |

## 3. Dirty Worktree Inventory

Tracked modifications:

- `android_client/README.md`
- `android_client/app/src/main/java/au/com/shyfted/client/DeviceConfig.java`
- `android_client/app/src/main/java/au/com/shyfted/client/MainActivity.java`

Untracked groups:

- Android source: `LcdPowerController.java`, `PresenceMonitor.java`.
- Android documentation and evidence: GPIO18 Phase 1/2/3 markdown, log, and `phase3_evidence/`.
- Android local tooling: `petey_gpio18_presence_logger.sh`.
- Hanshow durable docs: `docs/hanshow_capability_matrix.md`, `docs/hanshow_publish_sequence.md`.
- Hanshow starter/discovery bundle: `hanshow_integration_starter/`.

Ignored/generated groups:

- Python environment/cache: `.venv/`, `.pytest_cache/`, `__pycache__/`, `device_clients/__pycache__/`.
- Runtime data: `data/cms.db`, `static/uploads/`.
- Android build/cache: `android_client/.gradle/`, `android_client/app/build/`, `android_client/build/`.
- Android investigation outputs: `android_client/petey_*.txt`, APK/DEX/vendor decompile output under `android_client/phase2_geniatech/`.
- System metadata: `.DS_Store`.

## 4. Tracked Modifications

| Path | Subsystem | Apparent purpose | Deliberate | Complete | Content type | Long-term home | Commit now? | Move safety | Risks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `android_client/README.md` | ShyftTab Android client | Documents GPIO18 presence logger and disabled-by-default LCD proof of concept | Yes | Mostly complete for investigation | Documentation | Temporarily Command; later ShyftTab/device repo docs | Yes, with Android/Petey commit if source is accepted | Move preserves safely | Contains old local path example and prototype naming; update later during repo split |
| `android_client/app/src/main/java/au/com/shyfted/client/DeviceConfig.java` | ShyftTab Android client | Adds presence LCD power configuration flags and timeout | Yes | Appears coherent | Source code | Temporarily Command; later ShyftTab/device repo | Yes, with Android/Petey commit after Android build validation | Move preserves safely | Prototype capability should remain disabled by default; avoid commercialising Petey language |
| `android_client/app/src/main/java/au/com/shyfted/client/MainActivity.java` | ShyftTab Android client | Wires `PresenceMonitor` and `LcdPowerController` into app lifecycle when enabled | Yes | Appears coherent | Source code | Temporarily Command; later ShyftTab/device repo | Yes, with Android/Petey commit after Android build validation | Move preserves safely | Needs Android validation on known-good environment/device before relying on behaviour |

## 5. Untracked Files

| Path | Classification | Subsystem | Recommendation |
| --- | --- | --- | --- |
| `android_client/app/src/main/java/au/com/shyfted/client/LcdPowerController.java` | Source code | ShyftTab Android client | Commit with Android GPIO18 LCD proof-of-concept if approved; later split to ShyftTab/device repo |
| `android_client/app/src/main/java/au/com/shyfted/client/PresenceMonitor.java` | Source code | ShyftTab Android client | Commit with Android GPIO18 LCD proof-of-concept if approved; later split to ShyftTab/device repo |
| `android_client/docs/gpio18_power_management_phase1.md` | Documentation/evidence | Petey investigation | Commit if preserving investigation context; later move to ShyftTab/Petey engineering docs |
| `android_client/docs/gpio18_lcd_power_phase2.md` | Documentation/evidence | Petey investigation | Commit if preserving investigation context; later move to ShyftTab/Petey engineering docs |
| `android_client/docs/gpio18_lcd_power_phase3.md` | Documentation/evidence | Petey investigation | Commit if preserving investigation context; later move to ShyftTab/Petey engineering docs |
| `android_client/docs/gpio18_presence_phase1_capture_20260722.log` | Evidence log | Petey investigation | Preserve; consider commit only if log is useful evidence and contains no sensitive customer data |
| `android_client/docs/phase3_evidence/*.txt` | Evidence captures | Petey/RK3566 investigation | Preserve; commit only if needed for reproducible engineering record; later move to device reference/archive |
| `android_client/tools/petey_gpio18_presence_logger.sh` | Local device tooling | Petey investigation | Commit with Android proof-of-concept if approved; later split to ShyftTab/device tooling |
| `docs/hanshow_capability_matrix.md` | Durable architecture/documentation | Hanshow | Do not keep in Command long-term; relocate later to `~/Shyfted/docs/integrations/hanshow/` or `~/Shyfted/devices/hanshow/docs/` |
| `docs/hanshow_publish_sequence.md` | Durable architecture/documentation | Hanshow | Do not keep in Command long-term; relocate later to `~/Shyfted/docs/integrations/hanshow/` or `~/Shyfted/devices/hanshow/docs/` |
| `hanshow_integration_starter/*` | Mixed starter/source/reference | Hanshow | File-by-file disposition below; do not move now |

## 6. Ignored And Generated Material

| Path | Apparent purpose | Recommendation |
| --- | --- | --- |
| `.venv/` | Local Python virtual environment, 112M | Do not commit; preserve locally if needed; recreate after relocation if required |
| `.pytest_cache/`, `__pycache__/`, `device_clients/__pycache__/`, `hanshow_integration_starter/__pycache__/` | Python caches | Ignore; deletion candidate after approval |
| `data/cms.db` | Local SQLite runtime database | Do not commit; preserve locally; back up before relocation; review `DATABASE_URL` dependency |
| `static/uploads/` | Local upload/media runtime directory, currently empty | Do not commit; preserve or recreate runtime directory as needed |
| `android_client/.gradle/`, `android_client/app/build/`, `android_client/build/` | Gradle and APK build output | Do not commit; ignore; deletion candidate after approval |
| `android_client/petey_*.txt` | Petey investigation captures | Preserve locally; commit only if intentionally selected as evidence |
| `android_client/phase2_geniatech/**/*.apk`, `*.dex`, generated decompile directories | Vendor/device reverse-engineering output | Do not commit generated binaries; preserve as reference/archive candidate |
| `.DS_Store` | macOS metadata | Ignore; deletion candidate after approval |

## 7. Sensitive And Runtime Material

Observed sensitive/runtime classes:

- `.env.example` files exist at repo root and under `hanshow_integration_starter/`; these are examples, not real secret files.
- No `.env` file was listed in the repository tree by the audit.
- `data/cms.db` exists and is ignored; treat as runtime data that may contain local users, hashes, app records, or customer-like pilot data.
- `static/uploads/` exists and is ignored; currently no files were listed.
- Certificate bundle files exist inside `.venv/` as package data; these are generated dependency files, not project secrets.
- Hanshow source references environment variable names for credentials but no credential values were printed.
- Android APK/DEX/build outputs exist and are ignored.
- No keystore, private key, `.jks`, `.p12`, `.pfx`, `.pem`, `.key`, or `.crt` project credential files were found outside the local virtual environment certificate bundle.

Recommendations:

- Commit only example environment files, never real `.env`.
- Do not commit `data/cms.db`, runtime JSON state, uploads, generated previews, local logs, APKs, DEX files, Gradle caches, virtual environments, or Python caches.
- Before migration, back up `data/cms.db` and confirm whether it is still required for local validation.
- Treat Hanshow vendor PDFs/PPTX as reference material, not product source.

## 8. Command Responsibility Review

Shyft Command should keep:

- Dealership-facing CMS/application UX.
- Content/media selection, preview, and publish controls.
- Operational dashboards appropriate to branch/dealership users.
- In-app presentation of ShyftPing messages when that capability is integrated.

The current Flask application and templates belong in Command for now.

Concerns that should eventually move out of Command:

- Organisation, Site, Asset truth: Shyfted Core.
- Device connectivity interpretation, Jobs, Deployments, Events, Audit, and notification intent: Shyfted Core.
- Hardware-specific execution and protocols: device/integration repositories.
- Hanshow protocol handling and vendor authentication: dedicated Hanshow integration boundary.
- ShyftTab Android client: future ShyftTab/device repository after stabilisation.

Transitional duplication is acceptable while Core contracts mature, but Command must not become a competing source of truth for Organisation/Site/Asset state.

## 9. Android / ShyftTab Boundary Review

The Android work is currently active and deliberate. It contains:

- Tracked Android client source already in repo.
- New presence monitoring and LCD blank/restore source.
- GPIO18 evidence, test protocols, and local device tooling.
- Generated Gradle output and APK/DEX files that are correctly ignored.
- Petey-specific engineering references.

Recommendation:

- Keep Android work inside Command temporarily until the current prototype behaviour is committed and validated.
- Later split to a ShyftTab/device-client repository or `~/Shyfted/devices/shyfttab/`.
- Keep Petey/Franky as engineering-only prototype names. Customer-facing product language should be ShyftTab.
- Before splitting, confirm Android build command, SDK/JDK assumptions, package naming, runtime configuration, and the contract with Command/Core.

## 10. Hanshow Boundary Review

Hanshow material should not remain in the long-term Shyft Command repository. The durable conclusions should become integration documentation; exploratory source should move to experiments or a dedicated integration repository only if it becomes production-worthy; vendor files should move to reference/archive.

File-by-file disposition:

| Path | Hanshow category | Disposition |
| --- | --- | --- |
| `docs/hanshow_capability_matrix.md` | Durable architecture/documentation | Relocate later to `~/Shyfted/docs/integrations/hanshow/` or `~/Shyfted/devices/hanshow/docs/` |
| `docs/hanshow_publish_sequence.md` | Durable architecture/documentation | Relocate later to `~/Shyfted/docs/integrations/hanshow/` or `~/Shyfted/devices/hanshow/docs/` |
| `hanshow_integration_starter/.env.example` | Experimental source/tooling support | Keep only as example if starter is preserved; relocate with experiment; do not replace with real `.env` |
| `hanshow_integration_starter/.gitignore` | Experimental source/tooling support | Relocate with starter if preserved |
| `hanshow_integration_starter/CODY_INSTRUCTIONS.md` | Experimental discovery instructions | Relocate to `~/Shyfted/experiments/hanshow/` or archive with investigation record |
| `hanshow_integration_starter/Hanshow POC&Integration&Template Introduction.pptx` | Vendor/reference material | Relocate later to `~/Shyfted/devices/hanshow/reference/` or `~/Shyfted/Archive/hanshow-investigation/` |
| `hanshow_integration_starter/Hanshow-IntegrationProxy-OAuth2.0_V1.1.2.pdf` | Vendor/reference material | Relocate later to `~/Shyfted/devices/hanshow/reference/` or `~/Shyfted/Archive/hanshow-investigation/` |
| `hanshow_integration_starter/README.md` | Experimental source/tooling documentation | Relocate with starter to `~/Shyfted/experiments/hanshow/` unless promoted to integration repo |
| `hanshow_integration_starter/cli.py` | Experimental discovery tooling | Relocate to `~/Shyfted/experiments/hanshow/`; do not keep in Command long-term |
| `hanshow_integration_starter/config.py` | Experimental discovery tooling | Relocate to `~/Shyfted/experiments/hanshow/`; credential names only, no values printed |
| `hanshow_integration_starter/hanshow_client.py` | Experimental source/discovery client | Candidate for future production integration only after supported contract and tests; otherwise relocate to experiments |
| `hanshow_integration_starter/requirements.txt` | Experimental source dependency list | Relocate with starter |
| `hanshow_integration_starter/test_hanshow_client.py` | Experimental local test | Relocate with starter; dry-run-only test is useful |
| `hanshow_integration_starter/__pycache__/` | Generated/disposable | Deletion candidate after approval; do not commit |

Safety observations:

- The starter code supports dry-run mode.
- `python cli.py token` performs network authentication if credentials exist.
- `python cli.py push-sample` can perform a live product-data write if credentials/configuration are supplied.
- It does not document direct PDF/image/template/publish-status support.
- It should not be treated as production-worthy integration code yet.

## 11. Tests And Validation Available

Documented commands:

- Flask local run: `flask --app app run --host 0.0.0.0 --port 5050`.
- Production run: `gunicorn --bind 127.0.0.1:5050 app:app`.
- Android build: `gradle :app:assembleDebug` or `./gradlew :app:assembleDebug`.
- Android install/launch/logcat commands through ADB.
- Hanshow starter: `python cli.py token`, `python cli.py push-sample --dry-run`, `python cli.py push-sample`.

Validation not run during this audit:

- Flask startup/tests: not run to avoid creating/modifying SQLite runtime state.
- Android build/tests: not run because the task is read-only and build output already exists.
- Hanshow commands: not run because token/push require credentials/network and could touch external services.
- Hanshow unit test: not run to avoid changing cache state during the audit.

## 12. Proposed Commit Sequence

Commit 1:

- Message: `Document ShyftTab GPIO18 power investigation`
- Files: `android_client/README.md`, `android_client/docs/gpio18_power_management_phase1.md`, `android_client/docs/gpio18_lcd_power_phase2.md`, `android_client/docs/gpio18_lcd_power_phase3.md`, selected `android_client/docs/gpio18_presence_phase1_capture_20260722.log`, selected `android_client/docs/phase3_evidence/*.txt`
- Purpose: Preserve investigation record before migration.
- Validation first: manual review for sensitive/customer data in evidence; no Android build required for docs-only commit.
- Risk: Evidence logs may include device IPs, service listings, or environment details.
- Dustin approval: Yes.

Commit 2:

- Message: `Add ShyftTab presence-based LCD power proof of concept`
- Files: `android_client/app/src/main/java/au/com/shyfted/client/DeviceConfig.java`, `android_client/app/src/main/java/au/com/shyfted/client/MainActivity.java`, `android_client/app/src/main/java/au/com/shyfted/client/LcdPowerController.java`, `android_client/app/src/main/java/au/com/shyfted/client/PresenceMonitor.java`, `android_client/tools/petey_gpio18_presence_logger.sh`
- Purpose: Preserve disabled-by-default Android source/tooling.
- Validation first: `./gradlew :app:assembleDebug` or documented Gradle build in known-good Android environment; optional device smoke test if approved.
- Risk: Hardware-specific prototype code remains inside Command temporarily.
- Dustin approval: Yes.

Commit 3:

- Message: `Document Hanshow integration discovery`
- Files: `docs/hanshow_capability_matrix.md`, `docs/hanshow_publish_sequence.md`
- Purpose: Preserve durable integration conclusions before later relocation out of Command.
- Validation first: documentation review only.
- Risk: Docs reference NDA/vendor material; keep concise and avoid proprietary extracts.
- Dustin approval: Yes.

Commit 4:

- Message: `Preserve Hanshow integration starter experiment`
- Files: `hanshow_integration_starter/.env.example`, `.gitignore`, `CODY_INSTRUCTIONS.md`, `README.md`, `cli.py`, `config.py`, `hanshow_client.py`, `requirements.txt`, `test_hanshow_client.py`
- Purpose: Preserve experimental starter until relocated to experiments or a dedicated integration repository.
- Validation first: `python -m pytest hanshow_integration_starter/test_hanshow_client.py` in an isolated local environment, without real credentials.
- Risk: Starter can perform live writes if used with credentials and non-dry-run command.
- Dustin approval: Yes.

Do not commit:

- `hanshow_integration_starter/__pycache__/`
- `.venv/`, `.pytest_cache/`, `__pycache__/`
- `data/cms.db`
- `static/uploads/`
- Android Gradle/build outputs
- APK/DEX/generated decompile output
- `.DS_Store`

## 13. Files Not To Commit

- `.env` if it appears later.
- `data/cms.db` and any `data/*.db-*` files.
- `data/*.json` runtime state unless deliberately converted to seed/example data.
- `static/uploads/`, `uploads/`, `rendered/`, `previews/`, `cache/`.
- `.venv/`, `.pytest_cache/`, `__pycache__/`, `*.pyc`.
- `android_client/.gradle/`, `android_client/app/build/`, `android_client/build/`.
- `android_client/phase2_geniatech/**/*.apk`, generated `.dex`, generated decompile directories, and extracted vendor `.so` files.
- `android_client/petey_*.txt` unless individually approved as evidence.
- `hanshow_integration_starter/__pycache__/`.
- Real Hanshow credentials, tokens, screenshots containing secrets, or live response bodies containing sensitive values.

## 14. Path Dependencies

No references to the legacy `/Users/katmeintjes/Shyfted GitHub/shyfted_cms` path remain inside this repository.

References outside this repository were found but not modified:

- `/Users/katmeintjes/Shyfted/docs/directory-migration-manifest.md`
- `/Users/katmeintjes/Shyfted/core/shyfted-core/SHYFT_COMMAND_ECOSYSTEM_FIT.md`

Internal docs contain relative paths and one Android doc command with the current absolute repository path. That should be updated during relocation or device-repo split, not during this read-only audit.

## 15. Migration Readiness

Classification: **Ready after planned commits and runtime cleanup review**.

The Git branch and upstream are healthy, but the repo should not be relocated while its Android and Hanshow work remains uncommitted and unresolved. A raw filesystem move would preserve the dirty worktree, ignored files, and Git history, but it would make later review harder because path-sensitive documentation and local runtime state would be changing at the same time.

Minimum readiness checklist:

- Dustin approves which Android/Petey evidence is committed.
- Dustin approves whether Hanshow starter is committed temporarily or moved later uncommitted.
- Confirm `data/cms.db` backup and whether local database is still needed.
- Confirm no real `.env` exists.
- Run Android build if committing Android source.
- Run Hanshow unit test only in offline/dry-run mode if committing starter.
- Update migration manifest after the repository is actually moved.

## 16. Rollback And Preservation Notes

- Do not use `git reset`, `git clean`, or stash for this workstream without explicit approval.
- If a later relocation fails, move the whole repository directory back as one unit, preserving `.git`, ignored files, runtime data, and untracked work.
- Before any cleanup, create a file inventory and confirm backups for `data/cms.db`, Android evidence, and Hanshow vendor/reference files.
- Do not delete uncertain duplicates. Mark them as archive/deletion candidates and wait for approval.

## 17. Decisions Required From Dustin

1. Should the Android GPIO18 LCD proof-of-concept source be committed now, or kept uncommitted until a ShyftTab split?
2. Which Android evidence files should be committed versus preserved locally or archived?
3. Should the Hanshow durable docs be committed in Command temporarily before later relocation?
4. Should the Hanshow starter source be committed as an experiment, or kept uncommitted and moved later to `~/Shyfted/experiments/hanshow/`?
5. Should vendor PDFs/PPTX be preserved in Git anywhere, or stored only in reference/archive storage?
6. Is `data/cms.db` still needed for local validation before migration?
7. Should prototype naming in Android docs be cleaned before commit, or preserved as engineering evidence?

## 18. Recommended Next Action

Proceed to the separate controlled relocation step after Dustin approves the final status.

Do not move the repository as part of this stabilisation task.

## 19. Stabilisation Outcome

### Command Commits Created

| Commit | Purpose |
| --- | --- |
| `5c8ece5 Harden Command ignore and runtime boundaries` | Added explicit ignore rules for runtime state, Python caches, logs, archives, Android build output, local SDK config, APK/DEX outputs, and generated evidence. |
| `18939eb Add ShyftTab presence-based LCD power control` | Committed deliberate Android source, ShyftTab naming/default cleanup, disabled-by-default GPIO18 LCD power control, presence monitor, engineering docs, and the presence logger tool. |

### Android Files Committed

| Path | Final disposition |
| --- | --- |
| `android_client/README.md` | Committed; updated to ShyftTab naming and documented GPIO18 LCD proof of concept. |
| `android_client/app/src/main/java/au/com/shyfted/client/DeviceConfig.java` | Committed; added presence LCD configuration and changed persistent defaults from prototype naming to ShyftTab/generic values. |
| `android_client/app/src/main/java/au/com/shyfted/client/MainActivity.java` | Committed; wired presence/LCD power management and changed user-facing controls title to generic device language. |
| `android_client/app/src/main/java/au/com/shyfted/client/LcdPowerController.java` | Committed; new app-level LCD blank/restore proof-of-concept controller. |
| `android_client/app/src/main/java/au/com/shyfted/client/PresenceMonitor.java` | Committed; new GPIO18 presence monitor. |
| `android_client/app/src/main/res/values/strings.xml` | Committed; updated customer-facing labels to ShyftTab/generic device language. |
| `android_client/docs/gpio18_power_management_phase1.md` | Committed; retained engineering context and removed machine-specific repository path. |
| `android_client/docs/gpio18_lcd_power_phase2.md` | Committed; retained engineering test documentation and removed machine-specific SDK/JDK paths. |
| `android_client/docs/gpio18_lcd_power_phase3.md` | Committed; retained engineering investigation summary without committing raw evidence captures. |
| `android_client/tools/petey_gpio18_presence_logger.sh` | Committed; retained engineering-only Petey naming for prototype test tooling. |

### Android Files Excluded

| Path/group | Final disposition |
| --- | --- |
| `android_client/docs/gpio18_presence_phase1_capture_20260722.log` | Ignored; preserved locally as evidence/log material, not committed. |
| `android_client/docs/phase3_evidence/` | Ignored; preserved locally as generated/evidence captures, not committed. |
| `android_client/.gradle/`, `android_client/build/`, `android_client/app/build/` | Ignored; generated by Gradle, not committed. |
| `android_client/**/*.apk`, `android_client/**/*.dex` | Ignored; generated/vendor binary evidence, not committed. |
| `android_client/petey_*.txt` | Ignored; local prototype evidence, not committed. |
| `android_client/local.properties` | Ignored; machine-specific SDK config if created later. |

### Hanshow Files Moved Out Of Command

| Original path | Destination | Category |
| --- | --- | --- |
| `docs/hanshow_capability_matrix.md` | `/Users/katmeintjes/Shyfted/devices/hanshow/docs/hanshow_capability_matrix.md` | Durable knowledge |
| `docs/hanshow_publish_sequence.md` | `/Users/katmeintjes/Shyfted/devices/hanshow/docs/hanshow_publish_sequence.md` | Durable knowledge |
| `hanshow_integration_starter/.env.example` | `/Users/katmeintjes/Shyfted/devices/hanshow/experiments/.env.example` | Experimental tooling support |
| `hanshow_integration_starter/.gitignore` | `/Users/katmeintjes/Shyfted/devices/hanshow/experiments/.gitignore` | Experimental tooling support |
| `hanshow_integration_starter/CODY_INSTRUCTIONS.md` | `/Users/katmeintjes/Shyfted/devices/hanshow/experiments/CODY_INSTRUCTIONS.md` | Experimental discovery instructions |
| `hanshow_integration_starter/README.md` | `/Users/katmeintjes/Shyfted/devices/hanshow/experiments/README.md` | Experimental documentation |
| `hanshow_integration_starter/cli.py` | `/Users/katmeintjes/Shyfted/devices/hanshow/experiments/cli.py` | Experimental source/tooling |
| `hanshow_integration_starter/config.py` | `/Users/katmeintjes/Shyfted/devices/hanshow/experiments/config.py` | Experimental source/tooling |
| `hanshow_integration_starter/hanshow_client.py` | `/Users/katmeintjes/Shyfted/devices/hanshow/experiments/hanshow_client.py` | Experimental source/tooling |
| `hanshow_integration_starter/requirements.txt` | `/Users/katmeintjes/Shyfted/devices/hanshow/experiments/requirements.txt` | Experimental dependency list |
| `hanshow_integration_starter/test_hanshow_client.py` | `/Users/katmeintjes/Shyfted/devices/hanshow/experiments/test_hanshow_client.py` | Experimental local test |
| `hanshow_integration_starter/Hanshow-IntegrationProxy-OAuth2.0_V1.1.2.pdf` | `/Users/katmeintjes/Shyfted/devices/hanshow/reference/Hanshow-IntegrationProxy-OAuth2.0_V1.1.2.pdf` | Vendor/reference |
| `hanshow_integration_starter/Hanshow POC&Integration&Template Introduction.pptx` | `/Users/katmeintjes/Shyfted/devices/hanshow/reference/Hanshow POC&Integration&Template Introduction.pptx` | Vendor/reference |

Moved-file SHA-256 hashes were checked before and after relocation and matched.

### Files Deleted

| Path | Reason | Recoverability |
| --- | --- | --- |
| `hanshow_integration_starter/__pycache__/` | Generated Python bytecode cache; no unique findings. | Reproducible from preserved source. |
| Empty `hanshow_integration_starter/` directory | Empty after moving useful files. | Recreate if ever needed. |
| Empty `docs/` directory | Empty after moving Hanshow docs. | Recreate if ever needed. |

### Runtime Database Preservation

`data/cms.db` was not inspected and was not committed. A local backup was created at:

`/Users/katmeintjes/Shyfted/operations/backups/shyft-command/cms_20260803_2234.db`

The source and backup SHA-256 hashes matched.

### Validation Performed

| Check | Result |
| --- | --- |
| `git diff --cached --check` for committed changes | Passed |
| Android build without environment variables | Failed because SDK location was not configured in project/local environment |
| Android build with scoped `ANDROID_HOME` and `JAVA_HOME` | Passed: `./gradlew :app:assembleDebug` |
| Flask import smoke with existing `.venv` and temporary runtime paths | Passed: imported app and reported `Shyft Command` |
| Python tests | Not run; no repository Python test files were found after Hanshow experiment separation |
| Hanshow moved-file checksums | Passed |
| Search for Hanshow files remaining in Command | No active Hanshow files remain; audit document references remain intentionally |
| Runtime/generated staging check | No database, credential, APK, DEX, build output, cache, or log files were staged |

### Remaining Local Ignored Material

The following remain locally preserved and ignored:

- `.venv/`
- `.pytest_cache/`
- `__pycache__/`
- `data/cms.db`
- `static/uploads/`
- Android Gradle/build output
- Android evidence logs/captures
- Android APK/DEX/vendor generated artifacts
- `.DS_Store`

### Migration Readiness

Classification: **Ready for controlled repository relocation after approval**.

The Command repository itself now has the legitimate Android work committed and Hanshow active material removed. The remaining local runtime/generated files are ignored and should move with the repository only if the relocation plan intentionally preserves the complete local working directory.
