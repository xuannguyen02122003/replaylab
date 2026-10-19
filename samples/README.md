# Sample projects

Ordinary Python projects with **no ReplayLab code in them**. They exist to show that
`python -m tracer run` can record any script. You can also point it at your own code.

| Sample | What it does | Try |
|--------|--------------|-----|
| `invoice_report/` | Reads orders from a CSV, applies tax and discounts, prints a report | `orders.csv` works, `orders_bad.csv` crashes |
| `word_stats.py` | Counts words in a text file | An empty file crashes (division by zero) |

Run from the `backend` folder with its virtual environment active:

```powershell
python -m tracer run ..\samples\invoice_report\main.py
python -m tracer run ..\samples\invoice_report\main.py -- ..\samples\invoice_report\data\orders_bad.csv
python -m tracer run ..\samples\word_stats.py -- ..\samples\README.md
```
