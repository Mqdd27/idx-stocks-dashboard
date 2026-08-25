import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.calendar_import import import_holidays
if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else '/opt/stocks-dashboard/shared/market_calendar.json'
    import_holidays(path)
    print(f'calendar synced: {path}')
