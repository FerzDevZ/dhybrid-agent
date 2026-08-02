from dhybrid.agent.router import HybridRouter, classify_task
from dhybrid.efficiency.cache import PromptCache


def test_classify():
    assert classify_task("cari semua pemakaian fungsi x") == "small"
    assert classify_task("desain ulang arsitektur modul ini") == "big"
    assert classify_task("perbaiki bug yang bikin crash di parse") == "big"
    assert classify_task("jalankan pytest") == "small"
    assert classify_task("short") == "small"


def test_router_uses_small_for_mechanical(tmp_path):
    cache = PromptCache(db_path=tmp_path / "c.sqlite")
    router = HybridRouter(big_client="BIG", small_client="SMALL", cache=cache)
    assert router.route("jalankan pytest") == "SMALL"
    assert router.route("desain ulang arsitektur") == "BIG"
    assert router.stats == {"small": 1, "big": 1}
    # cache hit: klasifikasi tidak memanggil classifier lagi (stats konsisten)
    assert router.route("jalankan pytest") == "SMALL"
    assert router.stats == {"small": 2, "big": 1}


def test_router_force_big():
    router = HybridRouter(big_client="BIG", small_client="SMALL")
    assert router.route("cari x", force="big") == "BIG"
    assert router.stats == {"small": 0, "big": 1}
