#!/usr/bin/env python3
"""GitHub Actions Playwright 抓取测试脚本 v3

新增：
1. K 线翻页：通过向左滑动 canvas 加载更多历史数据
2. 筹码分布：保存完整数据并统计大小
3. 增加等待时间（筹码分布 5-10 秒）
"""

import json
import os
from playwright.sync_api import sync_playwright

GOODS_ID = "136"
DETAIL_URL = f"https://csqaq.com/goods/{GOODS_ID}"
RESULT_FILE = "result.json"
CHART_FILE = "chart_all_data.json"  # 完整 K 线数据
CHIP_FILE = "chip_all_data.json"  # 完整筹码分布数据

# K 线翻页次数（每次约 150 条日线 / 360 条 1 小时线）
CHART_SCROLL_TIMES = 5


def main():
    print("=" * 60, flush=True)
    print("  GitHub Actions Playwright 抓取测试 v3", flush=True)
    print(f"  饰品: goods_id={GOODS_ID}", flush=True)
    print(f"  K 线翻页次数: {CHART_SCROLL_TIMES}", flush=True)
    print("=" * 60, flush=True)

    result = {
        "test_env": {"runner": os.environ.get("RUNNER_OS", "unknown")},
        "good_id": GOODS_ID,
        "info": None,
        "chart_daily": None,
        "chart_1h": None,
        "chip_data": None,
        "debug": {
            "api_urls": [],
            "page_title": None,
            "chart_responses_count": {"daily": 0, "1h": 0},
            "chip_data_size_bytes": 0,
        },
        "errors": [],
    }

    # 完整数据存储
    all_chart_daily = []  # 所有日线数据
    all_chart_1h = []  # 所有 1 小时数据
    chip_full_data = None  # 完整筹码分布数据

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

            # 捕获所有 API 响应
            all_api_data = {}  # url -> list of responses
            chart_call_count = 0
            current_period = "unknown"  # 跟踪当前周期

            def handle_response(response):
                nonlocal chart_call_count
                url = response.url
                if "csqaq.com/proxies/api" not in url:
                    return
                try:
                    body = response.text()
                    if not body:
                        return
                    if url not in result["debug"]["api_urls"]:
                        result["debug"]["api_urls"].append(url)
                    if len(body) < 2000000:  # 2MB 限制
                        if url not in all_api_data:
                            all_api_data[url] = []
                        all_api_data[url].append({
                            "status": response.status,
                            "body": body,
                            "size": len(body),
                        })
                    if "chartAll" in url:
                        chart_call_count += 1
                except Exception:
                    pass

            page.on("response", handle_response)

            # 1. 访问详情页
            print("\n[1] 访问详情页...", flush=True)
            page.goto(DETAIL_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(8000)
            title = page.title()
            result["debug"]["page_title"] = title
            print(f"  标题: {title}", flush=True)

            # 2. 提取基本信息
            print("\n[2] 提取基本信息...", flush=True)
            for url, responses in all_api_data.items():
                if "info/good" in url:
                    last_resp = responses[-1]
                    try:
                        parsed = json.loads(last_resp["body"])
                        if parsed.get("code") == 200 and parsed.get("data"):
                            d = parsed["data"]
                            info_data = d.get("goods_info", d)
                            result["info"] = {
                                "name": info_data.get("name"),
                                "market_hash_name": info_data.get("market_hash_name"),
                                "exterior": info_data.get("exterior_localized_name"),
                                "buff_sell_price": info_data.get("buff_sell_price"),
                                "yyyp_sell_price": info_data.get("yyyp_sell_price"),
                                "yyyp_buy_price": info_data.get("yyyp_buy_price"),
                                "yyyp_sell_num": info_data.get("yyyp_sell_num"),
                                "steam_sell_price": info_data.get("steam_sell_price"),
                                "statistic": info_data.get("statistic"),
                                "turnover_number": info_data.get("turnover_number"),
                                "turnover_avg_price": info_data.get("turnover_avg_price"),
                                "sell_price_rate_1": info_data.get("sell_price_rate_1"),
                                "sell_price_rate_7": info_data.get("sell_price_rate_7"),
                                "sell_price_rate_30": info_data.get("sell_price_rate_30"),
                                "yyyp_sell_price_rate_1": info_data.get("yyyp_sell_price_rate_1"),
                                "yyyp_sell_price_rate_30": info_data.get("yyyp_sell_price_rate_30"),
                            }
                            print(f"  ✓ 名称: {result['info']['name']}", flush=True)
                            print(f"  ✓ 悠悠卖价: {result['info']['yyyp_sell_price']}", flush=True)
                            break
                    except Exception as e:
                        print(f"  解析失败: {e}", flush=True)

            # 3. 点击 K 线图
            print("\n[3] 点击 K 线图...", flush=True)
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

            # 4. 切换平台到悠悠有品
            print("\n[4] 切换平台到悠悠有品...", flush=True)
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
                page.wait_for_timeout(3000)
                print("  ✓ 切换完成", flush=True)

            # 5. 切换日线 + 翻页加载更多
            print(f"\n[5] 切换日线并翻页 {CHART_SCROLL_TIMES} 次...", flush=True)
            chart_url = "https://csqaq.com/proxies/api/v1/info/simple/chartAll"
            current_period = "daily"

            page.evaluate("""() => {
                const els = document.querySelectorAll('span, div, a, button');
                for (const el of els) {
                    if (el.textContent.trim() === '日线' && el.offsetParent !== null) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }""")
            page.wait_for_timeout(4000)

            # 收集第一次日线数据
            if chart_url in all_api_data and all_api_data[chart_url]:
                parsed = json.loads(all_api_data[chart_url][-1]["body"])
                if parsed.get("code") == 200:
                    arr = parsed.get("data", [])
                    if isinstance(arr, list):
                        all_chart_daily.extend(arr)
                        print(f"  初始日线: {len(arr)} 条", flush=True)

            # 获取 canvas 位置用于滑动
            canvas_info = page.evaluate("""() => {
                const canvas = document.querySelector('canvas');
                if (!canvas) return null;
                const rect = canvas.getBoundingClientRect();
                return {x: rect.x, y: rect.y, width: rect.width, height: rect.height};
            }""")
            print(f"  canvas: {canvas_info}", flush=True)

            # 向左滑动翻页
            if canvas_info:
                center_y = canvas_info["y"] + canvas_info["height"] / 2
                for i in range(CHART_SCROLL_TIMES):
                    before_count = chart_call_count
                    before_len = len(all_chart_daily)

                    # 从右向左拖动
                    start_x = canvas_info["x"] + canvas_info["width"] * 0.8
                    end_x = canvas_info["x"] + canvas_info["width"] * 0.2

                    page.mouse.move(start_x, center_y)
                    page.mouse.down()
                    steps = 20
                    for step in range(1, steps + 1):
                        x = start_x + (end_x - start_x) * step / steps
                        page.mouse.move(x, center_y)
                    page.mouse.up()
                    page.wait_for_timeout(3000)

                    # 收集新数据
                    if chart_url in all_api_data and len(all_api_data[chart_url]) > (len(all_chart_daily) // 150):
                        # 取最新的响应
                        latest_idx = len(all_api_data[chart_url]) - 1
                        parsed = json.loads(all_api_data[chart_url][latest_idx]["body"])
                        if parsed.get("code") == 200:
                            arr = parsed.get("data", [])
                            if isinstance(arr, list) and len(arr) > 0:
                                all_chart_daily.extend(arr)
                                print(f"  翻页 {i+1}: 新增 {len(arr)} 条, 总计 {len(all_chart_daily)} 条", flush=True)

                    # 也尝试滚轮
                    if chart_call_count == before_count:
                        page.mouse.move(canvas_info["x"] + canvas_info["width"] / 2, center_y)
                        page.mouse.wheel(-1000, 0)
                        page.wait_for_timeout(2000)
                        if chart_url in all_api_data:
                            latest_idx = len(all_api_data[chart_url]) - 1
                            parsed = json.loads(all_api_data[chart_url][latest_idx]["body"])
                            if parsed.get("code") == 200:
                                arr = parsed.get("data", [])
                                if isinstance(arr, list) and len(arr) > 0:
                                    all_chart_daily.extend(arr)
                                    print(f"  滚轮 {i+1}: 新增 {len(arr)} 条, 总计 {len(all_chart_daily)} 条", flush=True)

            # 去重（按时间戳 t）
            seen_t = set()
            unique_daily = []
            for item in all_chart_daily:
                t = item.get("t")
                if t and t not in seen_t:
                    seen_t.add(t)
                    unique_daily.append(item)
            all_chart_daily = unique_daily
            # 按时间排序
            all_chart_daily.sort(key=lambda x: int(x.get("t", 0)))
            result["chart_daily"] = {
                "count": len(all_chart_daily),
                "first": all_chart_daily[0] if all_chart_daily else None,
                "last": all_chart_daily[-1] if all_chart_daily else None,
            }
            result["debug"]["chart_responses_count"]["daily"] = len(all_api_data.get(chart_url, []))
            print(f"  ✓ 日线总计: {len(all_chart_daily)} 条 (去重后)", flush=True)
            if all_chart_daily:
                import datetime
                first_t = int(all_chart_daily[0]["t"]) / 1000
                last_t = int(all_chart_daily[-1]["t"]) / 1000
                print(f"    时间范围: {datetime.datetime.fromtimestamp(first_t)} ~ {datetime.datetime.fromtimestamp(last_t)}", flush=True)

            # 6. 切换 1 小时 + 翻页
            print(f"\n[6] 切换 1 小时并翻页 {CHART_SCROLL_TIMES} 次...", flush=True)
            current_period = "1h"

            page.evaluate("""() => {
                const targets = ['1小时', '1H', '1h'];
                const els = document.querySelectorAll('span, div, a, button, li');
                for (const target of targets) {
                    for (const el of els) {
                        if (el.textContent.trim() === target && el.offsetParent !== null) {
                            el.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
            page.wait_for_timeout(4000)

            # 收集第一次 1 小时数据
            if chart_url in all_api_data and all_api_data[chart_url]:
                # 找到 1 小时的响应（最后一次）
                latest_idx = len(all_api_data[chart_url]) - 1
                parsed = json.loads(all_api_data[chart_url][latest_idx]["body"])
                if parsed.get("code") == 200:
                    arr = parsed.get("data", [])
                    if isinstance(arr, list):
                        all_chart_1h.extend(arr)
                        print(f"  初始 1 小时: {len(arr)} 条", flush=True)

            # 向左滑动翻页
            if canvas_info:
                center_y = canvas_info["y"] + canvas_info["height"] / 2
                for i in range(CHART_SCROLL_TIMES):
                    before_count = len(all_chart_1h)

                    start_x = canvas_info["x"] + canvas_info["width"] * 0.8
                    end_x = canvas_info["x"] + canvas_info["width"] * 0.2

                    page.mouse.move(start_x, center_y)
                    page.mouse.down()
                    for step in range(1, 21):
                        x = start_x + (end_x - start_x) * step / 20
                        page.mouse.move(x, center_y)
                    page.mouse.up()
                    page.wait_for_timeout(3000)

                    # 收集新数据
                    if chart_url in all_api_data:
                        latest_idx = len(all_api_data[chart_url]) - 1
                        parsed = json.loads(all_api_data[chart_url][latest_idx]["body"])
                        if parsed.get("code") == 200:
                            arr = parsed.get("data", [])
                            if isinstance(arr, list) and len(arr) > 0:
                                all_chart_1h.extend(arr)
                                print(f"  翻页 {i+1}: 新增 {len(arr)} 条, 总计 {len(all_chart_1h)} 条", flush=True)

                    if len(all_chart_1h) == before_count:
                        page.mouse.move(canvas_info["x"] + canvas_info["width"] / 2, center_y)
                        page.mouse.wheel(-1000, 0)
                        page.wait_for_timeout(2000)
                        if chart_url in all_api_data:
                            latest_idx = len(all_api_data[chart_url]) - 1
                            parsed = json.loads(all_api_data[chart_url][latest_idx]["body"])
                            if parsed.get("code") == 200:
                                arr = parsed.get("data", [])
                                if isinstance(arr, list) and len(arr) > 0:
                                    all_chart_1h.extend(arr)
                                    print(f"  滚轮 {i+1}: 新增 {len(arr)} 条, 总计 {len(all_chart_1h)} 条", flush=True)

            # 去重
            seen_t = set()
            unique_1h = []
            for item in all_chart_1h:
                t = item.get("t")
                if t and t not in seen_t:
                    seen_t.add(t)
                    unique_1h.append(item)
            all_chart_1h = unique_1h
            all_chart_1h.sort(key=lambda x: int(x.get("t", 0)))
            result["chart_1h"] = {
                "count": len(all_chart_1h),
                "first": all_chart_1h[0] if all_chart_1h else None,
                "last": all_chart_1h[-1] if all_chart_1h else None,
            }
            print(f"  ✓ 1 小时总计: {len(all_chart_1h)} 条 (去重后)", flush=True)

            # 7. 点击筹码分布图（等待 5-10 秒）
            print("\n[7] 点击筹码分布图（等待 8 秒）...", flush=True)
            chip_url = "https://csqaq.com/proxies/api/v1/info/chipData"

            chip_clicked = page.evaluate("""() => {
                const chipEl = document.querySelector('.chip_tag___2aXfK');
                if (chipEl) { chipEl.click(); return 'class'; }
                const els = document.querySelectorAll('span, div, a, button, li, p');
                for (const el of els) {
                    const text = el.textContent.trim();
                    if ((text === '筹码分布图' || text === '筹码分布' || text === '筹码') && el.offsetParent !== null) {
                        el.click();
                        return 'text:' + text;
                    }
                }
                return false;
            }""")
            print(f"  点击结果: {chip_clicked}", flush=True)
            page.wait_for_timeout(8000)  # 等待 8 秒

            # 如果没触发，二次尝试
            if chip_url not in all_api_data:
                print("  二次尝试点击筹码分布...", flush=True)
                page.evaluate("""() => {
                    const els = document.querySelectorAll('*');
                    for (const el of els) {
                        const text = el.textContent.trim();
                        if (text.includes('筹码') && text.length < 20 && el.offsetParent !== null && el.children.length === 0) {
                            el.click();
                            return text;
                        }
                    }
                    return false;
                }""")
                page.wait_for_timeout(8000)

            # 提取筹码分布完整数据
            if chip_url in all_api_data and all_api_data[chip_url]:
                last_resp = all_api_data[chip_url][-1]
                chip_body = last_resp["body"]
                chip_size = len(chip_body.encode("utf-8"))
                result["debug"]["chip_data_size_bytes"] = chip_size
                print(f"  ✓ 筹码分布 API 响应大小: {chip_size} bytes ({chip_size/1024:.1f} KB)", flush=True)

                parsed = json.loads(chip_body)
                if parsed.get("code") == 200 and parsed.get("data"):
                    d = parsed["data"]
                    chip_full_data = d
                    result["chip_data"] = {
                        "fields": list(d.keys()),
                        "date_count": len(d.get("date", [])),
                        "first_date": d.get("date", [None])[0],
                        "last_date": d.get("date", [None])[-1],
                        "data_size_bytes": chip_size,
                        "data_size_kb": round(chip_size / 1024, 1),
                        "sample_low": d.get("low", [])[:3],
                        "sample_high": d.get("high", [])[:3],
                        "sample_volume": d.get("volume", [])[:3],
                    }
                    print(f"  ✓ 筹码分布: {result['chip_data']['date_count']} 天", flush=True)
                    print(f"  ✓ 数据大小: {result['chip_data']['data_size_kb']} KB", flush=True)

            browser.close()

    except Exception as e:
        result["errors"].append(f"Playwright 运行失败: {type(e).__name__}: {e}")
        print(f"\n[FATAL] {type(e).__name__}: {e}", flush=True)

    # 保存结果摘要
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[8] 结果摘要已保存: {RESULT_FILE}", flush=True)

    # 保存完整 K 线数据
    chart_data = {
        "good_id": GOODS_ID,
        "daily": all_chart_daily,
        "hourly": all_chart_1h,
    }
    with open(CHART_FILE, "w", encoding="utf-8") as f:
        json.dump(chart_data, f, ensure_ascii=False)
    chart_size = os.path.getsize(CHART_FILE)
    print(f"[9] 完整 K 线数据已保存: {CHART_FILE} ({chart_size/1024:.1f} KB)", flush=True)

    # 保存完整筹码分布数据
    if chip_full_data:
        with open(CHIP_FILE, "w", encoding="utf-8") as f:
            json.dump(chip_full_data, f, ensure_ascii=False)
        chip_size = os.path.getsize(CHIP_FILE)
        print(f"[10] 完整筹码分布数据已保存: {CHIP_FILE} ({chip_size/1024:.1f} KB)", flush=True)

    # 汇总
    print("\n" + "=" * 60, flush=True)
    print("  测试汇总", flush=True)
    print("=" * 60, flush=True)
    print(f"  基本信息: {'✓' if result['info'] else '✗'}", flush=True)
    print(f"  日线数据: {'✓' if result['chart_daily'] else '✗'} - {result['chart_daily']['count'] if result['chart_daily'] else 0} 条", flush=True)
    print(f"  1小时数据: {'✓' if result['chart_1h'] else '✗'} - {result['chart_1h']['count'] if result['chart_1h'] else 0} 条", flush=True)
    print(f"  筹码分布: {'✓' if result['chip_data'] else '✗'} - {result['chip_data']['date_count'] if result['chip_data'] else 0} 天", flush=True)
    if result['chip_data']:
        print(f"  筹码分布大小: {result['chip_data']['data_size_kb']} KB", flush=True)
    print(f"  错误数: {len(result['errors'])}", flush=True)
    for err in result["errors"]:
        print(f"    - {err}", flush=True)


if __name__ == "__main__":
    main()
