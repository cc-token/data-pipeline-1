#!/usr/bin/env python3
"""GitHub Actions Playwright 抓取测试脚本

测试目标：验证 GitHub Actions 环境能否用 Playwright 抓取 CSQAQ 网页数据
- 基本信息（/proxies/api/v1/info/good）
- K 线数据（/proxies/api/v1/info/simple/chartAll）
- 筹码分布图（/proxies/api/v1/info/chipData）
"""

import json
import os
import time
from playwright.sync_api import sync_playwright

GOODS_ID = "136"  # AK-47 | 红线（略有磨损）
DETAIL_URL = f"https://csqaq.com/goods/{GOODS_ID}"
RESULT_FILE = "result.json"


def main():
    print("=" * 60)
    print("  GitHub Actions Playwright 抓取测试")
    print(f"  饰品: goods_id={GOODS_ID}")
    print("=" * 60)

    result = {
        "test_env": {
            "runner": os.environ.get("RUNNER_OS", "unknown"),
            "python": os.environ.get("python_version", ""),
        },
        "good_id": GOODS_ID,
        "info": None,
        "chart_daily": None,
        "chart_1h": None,
        "chip_data": None,
        "errors": [],
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="zh-CN",
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = context.new_page()

            # 捕获 API 响应
            api_responses = {}

            def handle_response(response):
                url = response.url
                if "csqaq.com/proxies/api" not in url:
                    return
                try:
                    body = response.text()
                    if not body or len(body) > 100000:
                        return
                    api_responses[url] = {
                        "status": response.status,
                        "body": body,
                    }
                except Exception:
                    pass

            page.on("response", handle_response)

            # 1. 访问详情页
            print("\n[1] 访问详情页...")
            page.goto(DETAIL_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(6000)
            print(f"  当前URL: {page.url}")
            print(f"  页面标题: {page.title()}")

            # 2. 提取基本信息
            print("\n[2] 提取基本信息...")
            info_url = f"https://csqaq.com/proxies/api/v1/info/good?id={GOODS_ID}"
            if info_url in api_responses:
                try:
                    info_data = json.loads(api_responses[info_url]["body"])
                    if info_data.get("code") == 200 and info_data.get("data"):
                        d = info_data["data"]
                        result["info"] = {
                            "name": d.get("name"),
                            "market_hash_name": d.get("market_hash_name"),
                            "exterior": d.get("exterior_localized_name"),
                            "buff_sell_price": d.get("buff_sell_price"),
                            "yyyp_sell_price": d.get("yyyp_sell_price"),
                            "yyyp_buy_price": d.get("yyyp_buy_price"),
                            "yyyp_sell_num": d.get("yyyp_sell_num"),
                            "steam_sell_price": d.get("steam_sell_price"),
                            "statistic": d.get("statistic"),
                            "turnover_number": d.get("turnover_number"),
                            "turnover_avg_price": d.get("turnover_avg_price"),
                            "sell_price_rate_1": d.get("sell_price_rate_1"),
                            "sell_price_rate_7": d.get("sell_price_rate_7"),
                            "sell_price_rate_30": d.get("sell_price_rate_30"),
                            "yyyp_sell_price_rate_1": d.get("yyyp_sell_price_rate_1"),
                            "yyyp_sell_price_rate_30": d.get("yyyp_sell_price_rate_30"),
                        }
                        print(f"  ✓ 名称: {result['info']['name']}")
                        print(f"  ✓ 悠悠卖价: {result['info']['yyyp_sell_price']}")
                        print(f"  ✓ 存世量: {result['info']['statistic']}")
                    else:
                        result["errors"].append(f"info API code={info_data.get('code')}, msg={info_data.get('msg')}")
                        print(f"  ✗ info API 异常: {info_data.get('msg')}")
                except Exception as e:
                    result["errors"].append(f"info 解析失败: {e}")
                    print(f"  ✗ 解析失败: {e}")
            else:
                result["errors"].append("info API 未被触发")
                print("  ✗ info API 未被触发")

            # 3. 点击 K 线图
            print("\n[3] 点击 K 线图...")
            try:
                page.evaluate("""() => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        if (btn.textContent.trim() === 'K线图') {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                page.wait_for_timeout(3000)
            except Exception as e:
                result["errors"].append(f"点击 K线图失败: {e}")

            # 4. 切换平台到悠悠有品
            print("\n[4] 切换平台到悠悠有品...")
            try:
                select_info = page.evaluate("""() => {
                    const selects = document.querySelectorAll('select');
                    for (const sel of selects) {
                        const options = Array.from(sel.options).map(o => ({text: o.text, value: o.value}));
                        if (options.some(o => o.text === '悠悠有品')) {
                            const yyyp = options.find(o => o.text === '悠悠有品');
                            return {value: yyyp.value};
                        }
                    }
                    return null;
                }""")
                if select_info:
                    page.evaluate("""(targetValue) => {
                        const selects = document.querySelectorAll('select');
                        for (const sel of selects) {
                            const options = Array.from(sel.options).map(o => o.text);
                            if (options.includes('悠悠有品')) {
                                sel.value = targetValue;
                                sel.dispatchEvent(new Event('change', {bubbles: true}));
                                sel.dispatchEvent(new Event('input', {bubbles: true}));
                                return true;
                            }
                        }
                        return false;
                    }""", select_info["value"])
                    page.wait_for_timeout(2500)
                    print("  ✓ 切换到悠悠有品")
            except Exception as e:
                result["errors"].append(f"切换平台失败: {e}")

            # 5. 切换日线
            print("\n[5] 切换日线周期...")
            try:
                page.evaluate("""() => {
                    const allElements = document.querySelectorAll('span, div, a, button');
                    for (const el of allElements) {
                        if (el.textContent.trim() === '日线' && el.offsetParent !== null) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                page.wait_for_timeout(3000)
            except Exception as e:
                result["errors"].append(f"切换日线失败: {e}")

            # 提取日线数据
            chart_url = "https://csqaq.com/proxies/api/v1/info/simple/chartAll"
            if chart_url in api_responses:
                try:
                    chart_data = json.loads(api_responses[chart_url]["body"])
                    if chart_data.get("code") == 200:
                        arr = chart_data.get("data", [])
                        result["chart_daily"] = {
                            "count": len(arr) if isinstance(arr, list) else 0,
                            "first": arr[0] if isinstance(arr, list) and arr else None,
                            "last": arr[-1] if isinstance(arr, list) and arr else None,
                        }
                        print(f"  ✓ 日线数据: {result['chart_daily']['count']} 条")
                except Exception as e:
                    result["errors"].append(f"日线解析失败: {e}")

            # 6. 切换 1 小时
            print("\n[6] 切换 1 小时周期...")
            try:
                page.evaluate("""() => {
                    const allElements = document.querySelectorAll('span, div, a, button');
                    for (const el of allElements) {
                        if (el.textContent.trim() === '1小时' && el.offsetParent !== null) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                page.wait_for_timeout(3000)
            except Exception as e:
                result["errors"].append(f"切换1小时失败: {e}")

            # 提取 1 小时数据（清空旧响应重新捕获）
            api_responses.clear()
            page.wait_for_timeout(2000)
            if chart_url in api_responses:
                try:
                    chart_data = json.loads(api_responses[chart_url]["body"])
                    if chart_data.get("code") == 200:
                        arr = chart_data.get("data", [])
                        result["chart_1h"] = {
                            "count": len(arr) if isinstance(arr, list) else 0,
                            "first": arr[0] if isinstance(arr, list) and arr else None,
                            "last": arr[-1] if isinstance(arr, list) and arr else None,
                        }
                        print(f"  ✓ 1小时数据: {result['chart_1h']['count']} 条")
                except Exception as e:
                    result["errors"].append(f"1小时解析失败: {e}")

            # 7. 点击筹码分布图
            print("\n[7] 点击筹码分布图...")
            try:
                page.evaluate("""() => {
                    const elements = document.querySelectorAll('.chip_tag___2aXfK, span');
                    for (const el of elements) {
                        if (el.textContent.trim() === '筹码分布图' && el.offsetParent !== null) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                page.wait_for_timeout(3000)
            except Exception as e:
                result["errors"].append(f"点击筹码分布图失败: {e}")

            # 提取筹码分布图数据
            chip_url = "https://csqaq.com/proxies/api/v1/info/chipData"
            if chip_url in api_responses:
                try:
                    chip_data = json.loads(api_responses[chip_url]["body"])
                    if chip_data.get("code") == 200 and chip_data.get("data"):
                        d = chip_data["data"]
                        result["chip_data"] = {
                            "fields": list(d.keys()),
                            "date_count": len(d.get("date", [])),
                            "first_date": d.get("date", [None])[0],
                            "last_date": d.get("date", [None])[-1],
                            "sample_low": d.get("low", [])[:3],
                            "sample_high": d.get("high", [])[:3],
                            "sample_volume": d.get("volume", [])[:3],
                        }
                        print(f"  ✓ 筹码分布: {result['chip_data']['date_count']} 天数据")
                except Exception as e:
                    result["errors"].append(f"筹码分布解析失败: {e}")

            browser.close()

    except Exception as e:
        result["errors"].append(f"Playwright 运行失败: {type(e).__name__}: {e}")
        print(f"\n[FATAL] {type(e).__name__}: {e}")

    # 保存结果
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[8] 结果已保存: {RESULT_FILE}")

    # 汇总
    print("\n" + "=" * 60)
    print("  测试汇总")
    print("=" * 60)
    print(f"  基本信息: {'✓' if result['info'] else '✗'}")
    print(f"  日线数据: {'✓' if result['chart_daily'] else '✗'}")
    print(f"  1小时数据: {'✓' if result['chart_1h'] else '✗'}")
    print(f"  筹码分布: {'✓' if result['chip_data'] else '✗'}")
    print(f"  错误数: {len(result['errors'])}")
    for err in result["errors"]:
        print(f"    - {err}")


if __name__ == "__main__":
    main()
