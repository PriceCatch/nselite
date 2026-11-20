"""The same methods without async, for plain scripts and notebooks.

Run: uv run python examples/07_sync.py
"""

from pathlib import Path

from nselite import NotAvailable, ReportKey, SyncNSE

with SyncNSE() as nse:  # one connection, reused across calls
    print(nse.status()[0]["marketStatus"])
    print(len(nse.equity_history("RELIANCE")), "RELIANCE sessions in the last 30 days")
    try:
        print(nse.download_report(ReportKey.CM_BLOCK_DEAL, Path("data/reports")))
    except NotAvailable:
        print("no block deals file today")
