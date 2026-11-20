"""Drop-in for scripts written for NseIndiaApi: old names, sync calls, same exceptions.

Run: uv run python examples/08_compat.py
"""

from datetime import date, timedelta
from pathlib import Path

from nselite.compat import NSE  # was: from nse import NSE

nse = NSE(Path("data/compat"), server=False)
try:
    day = date.today() - timedelta(days=1)
    try:
        print(nse.equityBhavcopy(day))
    except RuntimeError:  # nselite's NotAvailable subclasses RuntimeError, as before
        print(day, "has no bhavcopy (weekend, holiday or not published yet)")
    print(nse.holidays(type=nse.HOLIDAY_TRADING)["CM"][0])
    print(nse.lookup("infosys")["symbols"][0]["symbol"])  # old {"symbols": [...]} shape
finally:
    nse.exit()
