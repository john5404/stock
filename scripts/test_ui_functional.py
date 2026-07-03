#!/usr/bin/env python3
"""Functional smoke test for LandingAnalysisApp (headless)."""

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import app
from landing_analysis.strategies import STRATEGY_TEMPLATES


def assert_true(cond, msg: str):
    if not cond:
        raise AssertionError(msg)


def test_ui_flow():
  errors: list[str] = []

  def run_step(name: str, fn):
    try:
      fn()
      print(f"  OK  {name}")
    except Exception as exc:
      errors.append(f"{name}: {exc}")
      print(f"  FAIL {name}: {exc}")
      traceback.print_exc()

  root = app.LandingAnalysisApp()
  root.withdraw()  # hide window during tests

  def step_init():
    assert_true(root.status_var.get() == "就緒", "initial status")
    assert_true(root.header_ticker_var.get() == "尚未載入", "initial header ticker")
    assert_true(len(root.notebook.tabs()) == 3, "notebook tabs")
    assert_true(not root.custom_params_section.winfo_ismapped(), "custom params hidden by default")

  def step_load_data():
    root.ticker_search_var.set("AAPL")
    root.custom_ticker_var.set("AAPL")
    root.period_var.set(app.PERIOD_LABELS["6mo"])
    root.load_data()
    assert_true(root.df is not None and len(root.df) > 0, "dataframe loaded")
    assert_true("AAPL" in root.header_ticker_var.get(), "header ticker updated")
    assert_true(root.analysis is not None, "auto analysis after load")
    assert_true("落點分析完成" in root.status_var.get(), "analysis status after load")

  def step_analysis():
    root.run_analysis()
    assert_true(root.analysis is not None, "analysis result")
    assert_true(len(root.analysis.supports) > 0, "support levels")
    assert_true(len(root.analysis.resistances) > 0, "resist levels")
    assert_true(root.levels_canvas is not None, "scheme C canvas")
    assert_true(root._levels_default_ylim is not None, "zoom defaults captured")
    assert_true("落點分析完成" in root.status_var.get(), "analysis status")

  def step_backtest_rolling():
    root.backtest_mode_var.set(app.BACKTEST_MODE_LABELS["rolling"])
    root.run_backtest()
    assert_true(root.backtest_result is not None, "backtest result")
    assert_true(len(root.trade_tree.get_children()) >= 0, "trade tree accessible")
    assert_true("回測完成" in root.status_var.get(), "backtest status")

  def step_backtest_fixed():
    root.backtest_mode_var.set(app.BACKTEST_MODE_LABELS["fixed"])
    root.run_backtest()
    assert_true(root.backtest_result.mode == "fixed", "fixed mode result")

  def step_run_all():
    root.ticker_search_var.set("MU")
    root.custom_ticker_var.set("MU")
    root.run_all()
    assert_true(root.df is not None, "run_all loaded data")
    assert_true(root.analysis is not None, "run_all analysis")
    assert_true(root.backtest_result is not None, "run_all backtest")

  def step_strategy_templates():
    for name in STRATEGY_TEMPLATES:
      root.strategy_var.set(name)
      root._apply_strategy_template(name)
      cfg = root._build_config_from_ui()
      assert_true(cfg.name == name, f"config name for {name}")
      assert_true(root.strategy_desc_var.get(), f"description for {name}")

  def step_custom_params():
    root.strategy_var.set("自訂")
    root._apply_strategy_template("自訂")
    root._param_vars["stop_loss_pct"].set(10)
    root._param_vars["rsi_buy"].set(35)
    root._on_custom_param_change()
    cfg = root._build_config_from_ui()
    assert_true(abs(cfg.stop_loss_pct - 0.10) < 1e-6, "custom stop loss")
    assert_true(cfg.rsi_buy == 35, "custom rsi buy")

  def step_ticker_preset():
    root.strategy_var.set("熱門股")
    root._apply_strategy_template("熱門股")
    assert_true(len(root._ticker_search_values) > 0, "preset tickers")
    root.ticker_search_var.set(root._ticker_search_values[0])
    root._on_ticker_search_select()
    assert_true(root.custom_ticker_var.get().strip(), "preset sets ticker")

  def step_tw_market_search():
    root.ticker_search_var.set("台積")
    root._on_ticker_search_key()
    assert_true(root.market_badge_var.get() == "台股", "market badge tw")
    assert_true(any(".TW" in sym or ".TWO" in sym for sym in root._ticker_catalog.values()), "tw catalog on chinese query")
    filtered = root._filter_ticker_search_values("台積")
    assert_true(any("台積電" in label for label in filtered), "tw search filter")
    root.ticker_search_var.set("2330")
    root.custom_ticker_var.set("2330")
    assert_true(root._resolve_ticker() == "2330.TW", "tw ticker normalize")
    root.ticker_search_var.set("AAPL")
    root._on_ticker_search_key()
    assert_true(any(sym == "AAPL" for sym in root._ticker_catalog.values()), "us catalog on english query")
    root.custom_ticker_var.set("AAPL")
    assert_true(root._resolve_ticker() == "AAPL", "us ticker normalize")

  def step_chart_draw():
    root._draw_price_chart()
    root._draw_levels_scheme_c()
    root._draw_empty_levels_chart()
    root._draw_empty_chart()
    root.df = None
    root._draw_price_chart()
    assert_true(root.canvas is not None, "chart canvas")
    assert_true(root.levels_canvas is not None, "levels canvas")

  print("LandingAnalysisApp functional tests")
  run_step("init", step_init)
  run_step("load_data", step_load_data)
  run_step("run_analysis", step_analysis)
  run_step("backtest_rolling", step_backtest_rolling)
  run_step("backtest_fixed", step_backtest_fixed)
  run_step("run_all", step_run_all)
  run_step("strategy_templates", step_strategy_templates)
  run_step("custom_params", step_custom_params)
  run_step("ticker_preset", step_ticker_preset)
  run_step("tw_market_search", step_tw_market_search)
  run_step("chart_draw", step_chart_draw)

  root.destroy()

  if errors:
    print(f"\n{len(errors)} test(s) failed:")
    for e in errors:
      print(f"  - {e}")
    sys.exit(1)

  print("\nAll functional tests passed.")


if __name__ == "__main__":
  test_ui_flow()
