"""Configure the disposable application account before test collection."""

import os

os.environ.setdefault("SHOP_DEMO_PASSWORD", "test-only-shopper-password")
