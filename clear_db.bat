@echo off
python -c "from scraper.database.db_cleanup import clear_all_data_from_db; clear_all_data_from_db()"
pause 