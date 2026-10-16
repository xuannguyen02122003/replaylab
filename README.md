# ReplayLab

Interactive debugging and execution replay platform.

> Work in progress. Nothing below is finished until it is listed under "Implemented".

## Implemented

- Event schema (`docs/event-schema.md`) and its Pydantic validation (`backend/app/schemas/event.py`), with tests

## Planned

- Instrumented Python demo app
- FastAPI collector with SQLite storage
- React trace explorer, recorded replay, run comparison

## Running the backend tests

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
```
