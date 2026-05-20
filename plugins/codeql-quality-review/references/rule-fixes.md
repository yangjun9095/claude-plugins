# CodeQL Python Code Quality — rule-by-rule fix playbook

Practical fixes for each CodeQL Python quality rule, ordered by severity. The
columns:
- **Rule** — CodeQL rule id (matches what appears in SARIF and on `/security/quality`)
- **Severity** — CodeQL's classification
- **Fix strategy** — what to do; often a `ruff` auto-fix exists, otherwise a manual pattern
- **Notes** — gotchas / false-positive caveats

## Reliability (genuine bugs)

| Rule | Severity | Fix strategy | Notes |
|---|---|---|---|
| `py/uninitialized-local-variable` | Warning/Error | Initialize the variable at function top (`x = None`) before the if/elif chain that may assign it. If `None` would be invalid downstream, add an explicit `if x is None: raise ValueError(...)` guard before use. | CodeQL's flow analysis is conservative about `try/except` — even if every branch assigns the variable on success, the rule fires when an exception path might skip the assignment. Defensive init + raise satisfies the analyzer AND surfaces real bugs. |
| `py/empty-except` | Note | Replace bare `except: pass` with either (a) narrow exception type + log/handle, or (b) narrow type + `pass` with explanatory comment. | The empty body is the smell, not the bare `except` per se — but address both. |
| `py/catch-base-exception` | Note | Narrow bare `except:` or `except BaseException:` to `except Exception:` (catches errors but not `KeyboardInterrupt`/`SystemExit`). Narrower types (e.g., `except (KeyError, IndexError):`) are better when possible. | The `BaseException` catch hides signal interrupts; in long-running scripts this can mask user `Ctrl+C`. |
| `py/illegal-raise` / `py/raise-not-implemented` | Error | Raise a real exception type, not `True`/`NotImplemented`/etc. Use `NotImplementedError` (the class) not `NotImplemented` (the constant). | `raise NotImplemented` is a common Python footgun — `NotImplemented` is for `__eq__` return values, not raising. |
| `py/non-exception-in-except-clause` (illegal exception handler) | Warning | The handler type must be an Exception subclass. Common mistake: `except (KeyError, ValueError) or RuntimeError:` (a bool expression) — should be a tuple `except (KeyError, ValueError, RuntimeError):`. | Easy to miss; lints often catch this. |
| `py/illegal-raise-from` | Warning | The expression after `from` must be an exception instance or `None`. | Less common. |
| `py/non-standard-exception-special-method` | Note | Use the protocol-correct exception in dunder methods: `__getitem__` should raise `IndexError`/`KeyError`/`TypeError` (not `ValueError`); `__next__` raises `StopIteration`; `__hash__` raises `TypeError`; etc. | Important for Dataset / Mapping / Iterator classes — iteration protocols depend on specific exception types. |

## Reliability — function-call correctness

| Rule | Severity | Fix strategy |
|---|---|---|
| `py/call/wrong-named-argument`, `py/call/wrong-named-class-argument` | Error | A callsite passes a keyword argument the callee doesn't accept. Usually appears AFTER a refactor that renamed a parameter without updating callers. Search for `func_name(\` and `class_name(\` to find all callsites. |
| `py/call/wrong-arguments` | Warning | Number of positional args doesn't match signature. |

## Maintainability — clearly-actionable cleanups (use `ruff`)

| Rule | Severity | Ruff rule | Fix command |
|---|---|---|---|
| `py/unused-import` | Note | `F401` | `ruff check --fix --select F401 <paths>` — auto-fix. Use the official `ruff` from the project's conda env (e.g., `~/.conda/envs/<env>/bin/ruff`). |
| `py/unused-local-variable` | Note | `F841` | `ruff check --fix --select F841 <paths>` — auto-fix. For matplotlib `fig, ax = plt.subplots(...)` patterns where you don't actually need `fig`, ruff suggests prefixing or dropping. |
| `py/local-shadows-global` | Note | (manual) | Rename the inner var. Common pattern: list-comprehension iter var like `[gene for gene in ...]` shadows module-level `gene`. Rename to `g` / `gn` / `item` etc. |
| `py/ineffectual-statement` / `py/statement-no-effect` | Note | `B018` | For notebook cell-output displays (a bare `df.head()` or `ad.obs` at the end of a cell), wrap in `print(...)`. For genuine dead expressions, delete. **Mirror changes to the paired `.ipynb` cell** if there is one. |
| `py/explicit-returns-mixed-with-implicit-returns` | Note | `RET503` | Add an explicit `return None` (or `return <typed-value>`) at the missing branch so the function consistently returns the same shape. |
| `py/unused-global-variable` | Note | (manual) | Delete the assignment OR prefix with `_` (Python convention for intentional-unused). |

## Maintainability — `py/commented-out-code` (`ERA001` in ruff)

| Pattern | Strategy |
|---|---|
| 50–500+ line blocks of an "old version commented at the top of file" | Delete the entire range. The active code is below; git history preserves the dead block. |
| Alternative implementation commented next to active code (e.g., 5–20 lines) | Delete. Same justification. |
| `# print(x)` debug breadcrumbs | Delete. |
| Narrative comments that describe what's happening | **Don't touch** — CodeQL's `py/commented-out-code` is more conservative than ruff's `ERA001` and shouldn't flag these. If `ruff` does flag, you can usually ignore. |

## Maintainability — `py/unused-parameter`

⚠️ **CodeQL does NOT respect the `_`-prefix convention for unused params.**

Renaming `def f(x)` to `def f(_x)` does **not** clear the alert AND can
**break callers** that use keyword-argument syntax (`f(x=42)` → TypeError).

**Recommended strategy:** evaluate each finding, then either fix or dismiss:

| Category | What it usually is | Action |
|---|---|---|
| PyTorch Lightning callbacks: `batch_idx`, `outputs`, `batch` in `training_step` / `validation_step` / `test_step` / `on_train_batch_end` | Framework-required positional signature | **Dismiss** in UI as "Won't fix → Used in tests/elsewhere" with note "required by Lightning framework signature" |
| API-parity kept params (`augment_aggfunc`, `compare_func` in `predict_on_dataset` etc.) | Kept for compat with upstream | **Dismiss** as "Won't fix → False positive" |
| Stale parameters from earlier refactors (in analysis scripts) | Genuinely dead | **Remove** from signature AFTER verifying no callers use the kwarg syntax (`grep -rn 'func(.*\bPARAM\s*=' --include="*.py"`). |
| Removed feature dependencies (e.g., a `wandb_project` param after migrating to HuggingFace) | Removable, but requires updating all callers | **Remove** if the caller-update is small; otherwise document and dismiss. |

If you're tempted to do a bulk prefix-rename — don't. It increases CodeQL noise
and breaks code. Trust dismissal.

## Other Quality rules

| Rule | Strategy |
|---|---|
| `py/unreachable-statement` | Delete the unreachable code. Often appears as a block after `return`/`raise`/`if-else-all-return`. |
| `py/redundant-comparison` | Simplify (`x == True` → `x`, `x == None` → `x is None`). |
| `py/comparison-using-is` | Use `==` instead of `is` for value equality on operands that have `__eq__`. |
| `py/test-equals-none` | Replace `x == None` with `x is None`. |
| `py/multiple-definition` | Remove duplicate `def` / `class` (or rename). |
| `py/cyclic-import` | Refactor module structure. |

## Notebook-specific gotchas

CodeQL scans both:
- `.py` files (including jupytext-exported `.py`s next to `.ipynb`)
- `.ipynb` cell source code

This means a single bug in an `.ipynb` cell may appear **twice** in the SARIF
(once via the cell, once via the jupytext `.py` mirror). **Fix in both
locations** — editing only the `.py` lets the next `jupytext --sync` overwrite
your fix from the stale `.ipynb`.

If you want to permanently suppress the jupytext `.py` duplicates, add a
`paths-ignore` entry to `.github/codeql/codeql-config.yml` AND switch CodeQL
setup from "Default" to "Advanced" in repo Settings (Default setup ignores the
config file).

## Standard tab vs AI tab on `/security/quality`

- **Standard tab** = findings from `python-code-quality.qls` (≈40 rules, conservative).
- **AI tab** = findings from `python-code-quality-extended.qls` + Copilot-curated subset (the UI filters to a curated set). Includes everything in standard plus additional rules like `py/unused-parameter`, `py/uninitialized-local-variable`, `py/local-shadows-global`.

Both come from the same workflow's SARIF — there's no separate AI scanner.
