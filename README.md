# Euro Macromechanica (EMM) Backtest — Tools  
*economic calendar builder & minute data analyzer (code-only)*

> 🧭 This repository is part of the **Euro Macromechanica Backtest (EMM)** ecosystem.

---

## 📚 Related ecosystem
- Backtest results, strategy proof, data‑quality policy (headline/stress), integrity materials — *[euro-macromechanica-results](https://github.com/rleydev/euro-macromechanica-results/tree/main)*  
- Prepared aggregates/data for reproducibility — *[euro-macromechanica-backtest-data](https://github.com/rleydev/euro-macromechanica-backtest-data/tree/main)*

---

## 🧭 Purpose
**Two data-prep utilities** for backtesting and auditability:

- **economic calendar builder** — collects key macro releases (central banks/statistical offices), normalizes fields, and converts local release times to **UTC±00:00** (DST-aware).  
  _See field layout and intent in the [`README.md`](https://github.com/rleydev/euro-macromechanica-backtest-data/tree/main/economic_calendars/README.md).

- **minute data analyzer** — prepares minute series (HistData-compatible): dedup and corrupted-row cleanup, **UTC-5 (fixed) → UTC±00:00** conversion, and gap counting with emphasis on **5–10 minutes** (critical for M5 bar quality).  
  _Explanations and analysis results are in the [`README.md`](https://github.com/rleydev/euro-macromechanica-backtest-data/blob/main/analysis/README.md).

> The code is intentionally lean; some details are lightly polished. It was authored to be compiled/edited in **ChatGPT‑5 (Thinking & Pro modes)** **to accelerate refinements without excessive boilerplate**. For full transparency, the entire pipeline is reproducible: follow the links above to replicate the data analysis and collection—including all noted nuances—and verify the results.

---

> ℹ️ **code-only:** you fetch any real data yourself and use it under the **original providers’ terms**. This repository does **not** re‑license third‑party data.

---

## 🔐 Integrity artifacts
The tools support emitting **SHA‑256** manifests, `artifacts.sha256`, for input and output files. These digests let you **verify** that a published result was produced from the stated inputs (no file‑content changes).

**Verify on your machine:**
```bash
sha256sum -c artifacts.sha256
# macOS: shasum -a 256 -c artifacts.sha256
```
> Note: if manifest lines contain absolute paths, hashes remain valid; when needed, create a local copy with relative filenames and verify against it.

---

## ⚖️ License
**Apache‑2.0** (`LICENSE`) — for the source code in this repository.  
Any external data you use with these tools remains governed by its **original providers’ terms**.

---

## ✉️ Contact
GitHub: **@rleydev (thelaziestcat)** · email: **thelaziestcat@proton.me**
