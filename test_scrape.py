#!/usr/bin/env python3
"""GitHub Actions Playwright 抓取测试脚本 v4

优化：
1. 日线翻页：8 次滑动 + 滚轮组合，目标 600+ 条
2. 滑动距离调整：从 0.8→0.2 改为 0.9→0.1（更长距离）
3. 增加请求去重检测（避免重复数据）
4. 增加等待时间和重试机制
5. 1 小时线保持 360 条
"""

import json
import os
import datetime
from playwright.sync_api import sync_playwright

GOODS_ID = "136"
DETAIL_URL = f"https://csqaq.com/goods/{GOODS_ID}"
RESULT_FILE = "result.json"
CHART_FILE = "chart_all_data.json"
CHIP_FILE = "chip_all_data.json"

# K 线翻页次数
CHART_SCROLL_TIMES = 8


def main():
    print("=" * 60, flush=True)
    print("  GitHub Actions Playwright 抓取测试 v4", flush=True)
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
            "chart_daily_requests": 0,
            "chart_1h_requests": 0,
            "chip_data_size_bytes": 0,
            "scroll_log": [],
        },
        "errors": [],
    }

    all_chart_daily = []
    all_chart_1h = []
    chip_full_data = None

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
                    if len(body) < 2000000:
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
            chart_response_count_before = len(all_api_data.get(chart_url, []))
            if chart_url in all_api_data and all_api_data[chart_url]:
                parsed = json.loads(all_api_data[chart_url][-1]["body"])
                if parsed.get("code") == 200:
                    arr = parsed.get("data", [])
                    if isinstance(arr, list):
                        all_chart_daily.extend(arr)
                        print(f"  初始日线: {len(arr)} 条", flush=True)
                        if arr:
                            first_t = int(arr[0]["t"]) / 1000
                            last_t = int(arr[-1]["t"]) / 1000
                            print(f"    时间: {datetime.datetime.fromtimestamp(first_t)} ~ {datetime.datetime.fromtimestamp(last_t)}", flush=True)

            # 获取 canvas 位置
            canvas_info = page.evaluate("""() => {
                const canvas = document.querySelector('canvas');
                if (!canvas) return null;
                const rect = canvas.getBoundingClientRect();
                return {x: rect.x, y: rect.y, width: rect.width, height: rect.height};
            }""")
            print(f"  canvas: {canvas_info}", flush=True)

            # 翻页：组合滑动 + 滚轮
            if canvas_info:
                center_y = canvas_info["y"] + canvas_info["height"] / 2
                # 记录已处理的响应数量
                processed_count = len(all_api_data.get(chart_url, []))

                for i in range(CHART_SCROLL_TIMES):
                    before_total = len(all_chart_daily)
                    before_resp_count = len(all_api_data.get(chart_url, []))
                    scroll_log = {"round": i + 1, "method": "", "before": before_total, "after": 0, "new": 0}

                    # 方法 1: 长距离滑动 (0.9 → 0.1)
                    start_x = canvas_info["x"] + canvas_info["width"] * 0.9
                    end_x = canvas_info["x"] + canvas_info["width"] * 0.1

                    page.mouse.move(start_x, center_y)
                    page.mouse.down()
                    for step in range(1, 31):  # 30 步更平滑
                        x = start_x + (end_x - start_x) * step / 30
                        page.mouse.move(x, center_y)
                    page.mouse.up()
                    page.wait_for_timeout(3500)

                    # 检查是否有新响应
                    current_resp_count = len(all_api_data.get(chart_url, []))
                    if current_resp_count > before_resp_count:
                        # 有新响应，提取数据
                        for idx in range(before_resp_count, current_resp_count):
                            parsed = json.loads(all_api_data[chart_url][idx]["body"])
                            if parsed.get("code") == 200:
                                arr = parsed.get("data", [])
                                if isinstance(arr, list) and len(arr) > 0:
                                    all_chart_daily.extend(arr)
                                    scroll_log["method"] = "drag"
                                    first_t = int(arr[0]["t"]) / 1000
                                    print(f"  翻页 {i+1} [拖动]: +{len(arr)} 条, 总计 {len(all_chart_daily)} 条, 起始 {datetime.datetime.fromtimestamp(first_t)}", flush=True)

                    # 方法 2: 如果拖动没效果，尝试滚轮
                    if len(all_api_data.get(chart_url, [])) == before_resp_count:
                        page.mouse.move(canvas_info["x"] + canvas_info["width"] / 2, center_y)
                        # 多次滚轮
                        for _ in range(3):
                            page.mouse.wheel(-1500, 0)
                            page.wait_for_timeout(1000)
                        page.wait_for_timeout(2000)

                        current_resp_count = len(all_api_data.get(chart_url, []))
                        if current_resp_count > before_resp_count:
                            for idx in range(before_resp_count, current_resp_count):
                                parsed = json.loads(all_api_data[chart_url][idx]["body"])
                                if parsed.get("code") == 200:
                                    arr = parsed.get("data", [])
                                    if isinstance(arr, list) and len(arr) > 0:
                                        all_chart_daily.extend(arr)
                                        scroll_log["method"] = "wheel"
                                        first_t = int(arr[0]["t"]) / 1000
                                        print(f"  翻页 {i+1} [滚轮]: +{len(arr)} 条, 总计 {len(all_chart_daily)} 条, 起始 {datetime.datetime.fromtimestamp(first_t)}", flush=True)

                    # 方法 3: 如果还没效果，尝试键盘左箭头（不 click canvas，直接按键）
                    if len(all_api_data.get(chart_url, [])) == before_resp_count:
                        page.mouse.move(canvas_info["x"] + canvas_info["width"] / 2, center_y)
                        # 先 focus canvas 通过 JS
                        page.evaluate("""() => {
                            const canvas = document.querySelector('canvas');
                            if (canvas) {
                                canvas.focus();
                                canvas.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
                                canvas.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                            }
                        }""")
                        for _ in range(10):
                            page.keyboard.press("ArrowLeft")
                        page.wait_for_timeout(3000)

                        current_resp_count = len(all_api_data.get(chart_url, []))
                        if current_resp_count > before_resp_count:
                            for idx in range(before_resp_count, current_resp_count):
                                parsed = json.loads(all_api_data[chart_url][idx]["body"])
                                if parsed.get("code") == 200:
                                    arr = parsed.get("data", [])
                                    if isinstance(arr, list) and len(arr) > 0:
                                        all_chart_daily.extend(arr)
                                        scroll_log["method"] = "keyboard"
                                        first_t = int(arr[0]["t"]) / 1000
                                        print(f"  翻页 {i+1} [键盘]: +{len(arr)} 条, 总计 {len(all_chart_daily)} 条, 起始 {datetime.datetime.fromtimestamp(first_t)}", flush=True)

                    scroll_log["after"] = len(all_chart_daily)
                    scroll_log["new"] = len(all_chart_daily) - before_total
                    result["debug"]["scroll_log"].append(scroll_log)

                    # 如果连续 3 次没有新数据，停止
                    if len(all_chart_daily) == before_total:
                        print(f"  翻页 {i+1}: 无新数据", flush=True)
                        # 检查最近 3 次是否都没新增
                        recent = result["debug"]["scroll_log"][-3:]
                        if len(recent) >= 3 and all(r["new"] == 0 for r in recent):
                            print(f"  连续 3 次无新数据，停止翻页", flush=True)
                            break

            # 去重日线
            seen_t = set()
            unique_daily = []
            for item in all_chart_daily:
                t = item.get("t")
                if t and t not in seen_t:
                    seen_t.add(t)
                    unique_daily.append(item)
            all_chart_daily = unique_daily
            all_chart_daily.sort(key=lambda x: int(x.get("t", 0)))
            result["chart_daily"] = {
                "count": len(all_chart_daily),
                "first": all_chart_daily[0] if all_chart_daily else None,
                "last": all_chart_daily[-1] if all_chart_daily else None,
            }
            result["debug"]["chart_daily_requests"] = len(all_api_data.get(chart_url, []))
            print(f"\n  ✓ 日线总计: {len(all_chart_daily)} 条 (去重后)", flush=True)
            if all_chart_daily:
                first_t = int(all_chart_daily[0]["t"]) / 1000
                last_t = int(all_chart_daily[-1]["t"]) / 1000
                print(f"    时间范围: {datetime.datetime.fromtimestamp(first_t)} ~ {datetime.datetime.fromtimestamp(last_t)}", flush=True)
                days = (last_t - first_t) / 86400
                print(f"    跨度: {days:.0f} 天 ({days/365:.1f} 年)", flush=True)

            # 6. 切换 1 小时（不翻页，360 条即可）
            print(f"\n[6] 切换 1 小时...", flush=True)

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

            # 收集 1 小时数据（取最后一次响应）
            if chart_url in all_api_data and all_api_data[chart_url]:
                latest_idx = len(all_api_data[chart_url]) - 1
                parsed = json.loads(all_api_data[chart_url][latest_idx]["body"])
                if parsed.get("code") == 200:
                    arr = parsed.get("data", [])
                    if isinstance(arr, list):
                        all_chart_1h.extend(arr)
                        print(f"  ✓ 1 小时: {len(arr)} 条", flush=True)

            result["chart_1h"] = {
                "count": len(all_chart_1h),
                "first": all_chart_1h[0] if all_chart_1h else None,
                "last": all_chart_1h[-1] if all_chart_1h else None,
            }
            result["debug"]["chart_1h_requests"] = len(all_api_data.get(chart_url, [])) - result["debug"]["chart_daily_requests"]

            # 7. 点击筹码分布图（等待 8 秒）
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
            page.wait_for_timeout(8000)

            # 二次尝试
            if chip_url not in all_api_data:
                print("  二次尝试...", flush=True)
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
                print(f"  ✓ API 响应大小: {chip_size} bytes ({chip_size/1024:.1f} KB)", flush=True)

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
                    }
                    print(f"  ✓ 筹码分布: {result['chip_data']['date_count']} 天, {result['chip_data']['data_size_kb']} KB", flush=True)

            browser.close()

    except Exception as e:
        result["errors"].append(f"Playwright 运行失败: {type(e).__name__}: {e}")
        print(f"\n[FATAL] {type(e).__name__}: {e}", flush=True)

    # 保存结果
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
    print(f"[9] 完整 K 线数据: {CHART_FILE} ({chart_size/1024:.1f} KB)", flush=True)

    # 保存筹码分布
    if chip_full_data:
        with open(CHIP_FILE, "w", encoding="utf-8") as f:
            json.dump(chip_full_data, f, ensure_ascii=False)
        chip_size = os.path.getsize(CHIP_FILE)
        print(f"[10] 筹码分布数据: {CHIP_FILE} ({chip_size/1024:.1f} KB)", flush=True)

    # 汇总
    print("\n" + "=" * 60, flush=True)
    print("  测试汇总", flush=True)
    print("=" * 60, flush=True)
    print(f"  基本信息: {'✓' if result['info'] else '✗'}", flush=True)
    print(f"  日线数据: {'✓' if result['chart_daily'] else '✗'} - {result['chart_daily']['count'] if result['chart_daily'] else 0} 条", flush=True)
    print(f"  1小时数据: {'✓' if result['chart_1h'] else '✗'} - {result['chart_1h']['count'] if result['chart_1h'] else 0} 条", flush=True)
    print(f"  筹码分布: {'✓' if result['chip_data'] else '✗'} - {result['chip_data']['date_count'] if result['chip_data'] else 0} 天", flush=True)
    print(f"  日线请求次数: {result['debug']['chart_daily_requests']}", flush=True)
    print(f"  翻页日志: {result['debug']['scroll_log']}", flush=True)


if __name__ == "__main__":
    main()
