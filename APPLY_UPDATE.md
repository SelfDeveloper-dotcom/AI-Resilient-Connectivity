# Apply Dashboard Update v1.4.0

This update changes only the dashboard/API presentation layer. It does **not** overwrite your `data/`, `knowledge_base/source/`, model registries, configs, or local documents.

## Safest manual copy method

1. Stop the dashboard with `Ctrl+C`.
2. Extract this ZIP to a temporary folder.
3. In your live project root, replace:
   - `api.py`
4. Create the folder `templates` in the project root if it does not already exist, then copy:
   - `templates/dashboard.html`
5. Optional but recommended: copy:
   - `tests/test_dashboard_ui.py`
   - `VERSION`
   - `CHANGELOG.md`
6. Do **not** replace or delete:
   - `data/`
   - `knowledge_base/source/`
   - `models/`
   - `.env`
7. Run:
   ```powershell
   python -m unittest discover -s tests -v
   ```
8. Restart:
   ```powershell
   .\run_dashboard.bat
   ```
9. Open:
   - Sandbox: `http://127.0.0.1:8000/dashboard?mode=sandbox`
   - Real: `http://127.0.0.1:8000/dashboard?mode=real`

Expected tests for the matching v1.3.1/v1.3.x baseline plus this update: **24 tests, OK**.
