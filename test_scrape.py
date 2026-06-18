#!/usr/bin/env python3
"""GitHub Actions Playwright 批量抓取测试脚本 v5

测试 5 个饰品串行采集，验证完整链路
"""

import json
import os
import datetime
from playwright.sync_api import sync_playwright

# 5 个测试饰品 ID
GOODS_IDS = ["136", "134", "133", "135", "137"]
DETAIL_URL = "https://csqaq.com/goods/{goods_id}"
RESULT_FILE = "result.json"
CHART_FILE = "chart_all_data.json"
CHIP_FILE = "chip_all_data.json"

CHART_SCROLL_TIMES = 5


def scrape_one(page, context_data, goods_id):
    """抓取单个饰品数据"""
    print(f"\n{'='*60}", flush=True)
    print(f"  开始抓取饰品: goods_id={goods_id}", flush=True)
    print(f"{'='*60}", flush=True)

    detail_url = DETAIL_URL.format(goods_id=goods_id)
    item_result = {
        "good_id": goods_id,
        "info": None,
        "chart_daily": None,
        "chart_1h": None,
        "chip_data": None,
        "errors": [],
    }

    # 每个饰品独立的 API 响应存储
    all_api_data = {}
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

    all_chart_daily = []
    all_chart_1h = []
    chip_full_data = None

    try:
        # 1. 访问详情页
        print(f"\n  [1] 访问详情页...", flush=True)
        page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(8000)
        title = page.title()
        print(f"      标题: {title}", flush=True)

        # 2. 提取基本信息
        print(f"  [2] 提取基本信息...", flush=True)
        for url, responses in all_api_data.items():
            if "info/good" in url:
                last_resp = responses[-1]
                try:
                    parsed = json.loads(last_resp["body"])
                    if parsed.get("code") == 200 and parsed.get("data"):
                        d = parsed["data"]
                        info_data = d.get("goods_info", d)
                        item_result["info"] = {
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
                        print(f"      ✓ 名称: {item_result['info']['name']}", flush=True)
                        print(f"      ✓ 悠悠卖价: {item_result['info']['yyyp_sell_price']}", flush=True)
                        break
                except Exception as e:
                    print(f"      解析失败: {e}", flush=True)

        # 3. 点击 K 线图
        print(f"  [3] 点击 K 线图...", flush=True)
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
        print(f"  [4] 切换平台到悠悠有品...", flush=True)
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
            print(f"      ✓ 切换完成", flush=True)

        # 5. 切换日线 + 翻页
        print(f"  [5] 切换日线并翻页 {CHART_SCROLL_TIMES} 次...", flush=True)
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

        # 收集初始日线
        if chart_url in all_api_data and all_api_data[chart_url]:
            parsed = json.loads(all_api_data[chart_url][-1]["body"])
            if parsed.get("code") == 200:
                arr = parsed.get("data", [])
                if isinstance(arr, list):
                    all_chart_daily.extend(arr)
                    print(f"      初始日线: {len(arr)} 条", flush=True)

        # 获取 canvas
        canvas_info = page.evaluate("""() => {
            const canvas = document.querySelector('canvas');
            if (!canvas) return null;
            const rect = canvas.getBoundingClientRect();
            return {x: rect.x, y: rect.y, width: rect.width, height: rect.height};
        }""")

        # 翻页
        if canvas_info:
            center_y = canvas_info["y"] + canvas_info["height"] / 2
            no_new_count = 0

            for i in range(CHART_SCROLL_TIMES):
                before_total = len(all_chart_daily)
                before_resp_count = len(all_api_data.get(chart_url, []))

                # 滚轮方式（最有效）
                page.mouse.move(canvas_info["x"] + canvas_info["width"] / 2, center_y)
                for _ in range(3):
                    page.mouse.wheel(-1500, 0)
                    page.wait_for_timeout(1000)
                page.wait_for_timeout(2000)

                # 收集新数据
                current_resp_count = len(all_api_data.get(chart_url, []))
                if current_resp_count > before_resp_count:
                    for idx in range(before_resp_count, current_resp_count):
                        parsed = json.loads(all_api_data[chart_url][idx]["body"])
                        if parsed.get("code") == 200:
                            arr = parsed.get("data", [])
                            if isinstance(arr, list) and len(arr) > 0:
                                all_chart_daily.extend(arr)
                                print(f"      翻页 {i+1} [滚轮]: +{len(arr)} 条, 总计 {len(all_chart_daily)} 条", flush=True)

                if len(all_chart_daily) == before_total:
                    no_new_count += 1
                    if no_new_count >= 2:
                        print(f"      连续无新数据，停止翻页", flush=True)
                        break
                else:
                    no_new_count = 0

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
        item_result["chart_daily"] = {
            "count": len(all_chart_daily),
            "first": all_chart_daily[0] if all_chart_daily else None,
            "last": all_chart_daily[-1] if all_chart_daily else None,
        }
        print(f"      ✓ 日线总计: {len(all_chart_daily)} 条", flush=True)

        # 6. 切换 1 小时
        print(f"  [6] 切换 1 小时...", flush=True)
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

        if chart_url in all_api_data and all_api_data[chart_url]:
            latest_idx = len(all_api_data[chart_url]) - 1
            parsed = json.loads(all_api_data[chart_url][latest_idx]["body"])
            if parsed.get("code") == 200:
                arr = parsed.get("data", [])
                if isinstance(arr, list):
                    all_chart_1h.extend(arr)
                    print(f"      ✓ 1 小时: {len(arr)} 条", flush=True)

        item_result["chart_1h"] = {
            "count": len(all_chart_1h),
            "first": all_chart_1h[0] if all_chart_1h else None,
            "last": all_chart_1h[-1] if all_chart_1h else None,
        }

        # 7. 筹码分布
        print(f"  [7] 点击筹码分布图（等待 8 秒）...", flush=True)
        chip_url = "https://csqaq.com/proxies/api/v1/info/chipData"

        page.evaluate("""() => {
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
        page.wait_for_timeout(8000)

        if chip_url not in all_api_data:
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

        if chip_url in all_api_data and all_api_data[chip_url]:
            last_resp = all_api_data[chip_url][-1]
            chip_body = last_resp["body"]
            chip_size = len(chip_body.encode("utf-8"))
            parsed = json.loads(chip_body)
            if parsed.get("code") == 200 and parsed.get("data"):
                d = parsed["data"]
                chip_full_data = d
                item_result["chip_data"] = {
                    "fields": list(d.keys()),
                    "date_count": len(d.get("date", [])),
                    "first_date": d.get("date", [None])[0],
                    "last_date": d.get("date", [None])[-1],
                    "data_size_bytes": chip_size,
                    "data_size_kb": round(chip_size / 1024, 1),
                }
                print(f"      ✓ 筹码分布: {item_result['chip_data']['date_count']} 天, {item_result['chip_data']['data_size_kb']} KB", flush=True)

    except Exception as e:
        item_result["errors"].append(f"{type(e).__name__}: {e}")
        print(f"  [ERROR] {type(e).__name__}: {e}", flush=True)

    # 移除监听器
    page.remove_listener("response", handle_response)

    return item_result, all_chart_daily, all_chart_1h, chip_full_data


def main():
    print("=" * 60, flush=True)
    print("  GitHub Actions Playwright 批量抓取测试 v5", flush=True)
    print(f"  饰品数量: {len(GOODS_IDS)} 个 (串行)", flush=True)
    print(f"  饰品 ID: {GOODS_IDS}", flush=True)
    print("=" * 60, flush=True)

    start_time = datetime.datetime.now()
    result = {
        "test_env": {"runner": os.environ.get("RUNNER_OS", "unknown")},
        "goods_ids": GOODS_IDS,
        "start_time": start_time.isoformat(),
        "items": [],
        "summary": {},
    }

    all_chart_data = {}
    all_chip_data = {}

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

            for idx, goods_id in enumerate(GOODS_IDS):
                print(f"\n{'#'*60}", flush=True)
                print(f"  进度: {idx+1}/{len(GOODS_IDS)} - goods_id={goods_id}", flush=True)
                print(f"{'#'*60}", flush=True)

                item_start = datetime.datetime.now()
                item_result, chart_daily, chart_1h, chip_data = scrape_one(page, {}, goods_id)
                item_end = datetime.datetime.now()
                item_result["duration_seconds"] = (item_end - item_start).total_seconds()

                result["items"].append(item_result)
                all_chart_data[goods_id] = {"daily": chart_daily, "hourly": chart_1h}
                if chip_data:
                    all_chip_data[goods_id] = chip_data

                print(f"\n  耗时: {item_result['duration_seconds']:.1f}s", flush=True)
                print(f"  基本信息: {'✓' if item_result['info'] else '✗'}", flush=True)
                print(f"  日线: {'✓' if item_result['chart_daily'] else '✗'} - {item_result['chart_daily']['count'] if item_result['chart_daily'] else 0} 条", flush=True)
                print(f"  1小时: {'✓' if item_result['chart_1h'] else '✗'} - {item_result['chart_1h']['count'] if item_result['chart_1h'] else 0} 条", flush=True)
                print(f"  筹码分布: {'✓' if item_result['chip_data'] else '✗'} - {item_result['chip_data']['date_count'] if item_result['chip_data'] else 0} 天", flush=True)

            browser.close()

    except Exception as e:
        print(f"\n[FATAL] {type(e).__name__}: {e}", flush=True)

    end_time = datetime.datetime.now()
    result["end_time"] = end_time.isoformat()
    result["total_duration_seconds"] = (end_time - start_time).total_seconds()

    # 汇总
    success_count = sum(1 for item in result["items"] if item["info"])
    result["summary"] = {
        "total": len(GOODS_IDS),
        "success": success_count,
        "failed": len(GOODS_IDS) - success_count,
        "total_duration": round(result["total_duration_seconds"], 1),
        "avg_duration": round(result["total_duration_seconds"] / len(GOODS_IDS), 1),
    }

    # 保存结果
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    with open(CHART_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chart_data, f, ensure_ascii=False)

    with open(CHIP_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chip_data, f, ensure_ascii=False)

    # 汇总输出
    print(f"\n{'='*60}", flush=True)
    print(f"  批量抓取汇总", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  总数: {result['summary']['total']}", flush=True)
    print(f"  成功: {result['summary']['success']}", flush=True)
    print(f"  失败: {result['summary']['failed']}", flush=True)
    print(f"  总耗时: {result['summary']['total_duration']}s", flush=True)
    print(f"  平均: {result['summary']['avg_duration']}s/个", flush=True)
    print(f"\n  各饰品详情:", flush=True)
    for item in result["items"]:
        name = item["info"]["name"] if item["info"] else "N/A"
        daily = item["chart_daily"]["count"] if item["chart_daily"] else 0
        h1 = item["chart_1h"]["count"] if item["chart_1h"] else 0
        chip = item["chip_data"]["date_count"] if item["chip_data"] else 0
        print(f"    [{item['good_id']}] {name}: 日线{daily} 1h{h1} 筹码{chip}天 耗时{item['duration_seconds']:.0f}s", flush=True)


if __name__ == "__main__":
    main()
