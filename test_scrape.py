#!/usr/bin/env python3
"""GitHub Actions Playwright 抓取测试脚本 v2

修复：
1. info API 匹配改为关键字匹配
2. 1小时数据不用 clear，改用请求计数
3. 筹码分布图增加等待时间和选择器
4. 增加调试输出
"""

import json
import os
import time
from playwright.sync_api import sync_playwright

GOODS_ID = "136"
DETAIL_URL = f"https://csqaq.com/goods/{GOODS_ID}"
RESULT_FILE = "result.json"


def main():
    print("=" * 60, flush=True)
    print("  GitHub Actions Playwright 抓取测试 v2", flush=True)
    print(f"  饰品: goods_id={GOODS_ID}", flush=True)
    print("=" * 60, flush=True)

    result = {
        "test_env": {
            "runner": os.environ.get("RUNNER_OS", "unknown"),
        },
        "good_id": GOODS_ID,
        "info": None,
        "chart_daily": None,
        "chart_1h": None,
        "chip_data": None,
        "debug": {
            "api_urls": [],
            "page_title": None,
        },
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
                    # 记录所有 API URL
                    if url not in result["debug"]["api_urls"]:
                        result["debug"]["api_urls"].append(url)
                    # 保存响应（提高大小限制到 1MB），用列表存储多次请求
                    if len(body) < 1000000:
                        if url not in all_api_data:
                            all_api_data[url] = []
                        all_api_data[url].append({
                            "status": response.status,
                            "body": body,
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
            print(f"  已捕获 API 数: {len(all_api_data)}", flush=True)

            # 2. 提取基本信息 - 遍历所有捕获的 API 找 info/good
            print("\n[2] 提取基本信息...", flush=True)
            info_data = None
            for url, responses in all_api_data.items():
                if "info/good" in url:
                    # 取最后一个响应
                    last_resp = responses[-1]
                    try:
                        parsed = json.loads(last_resp["body"])
                        # 保存完整响应用于调试
                        result["debug"]["info_raw"] = {
                            "code": parsed.get("code"),
                            "msg": parsed.get("msg"),
                            "data_keys": list(parsed.get("data", {}).keys()) if isinstance(parsed.get("data"), dict) else None,
                        }
                        if parsed.get("code") == 200 and parsed.get("data"):
                            d = parsed["data"]
                            # 数据结构: data.goods_info 才是饰品信息
                            if "goods_info" in d:
                                info_data = d["goods_info"]
                            else:
                                info_data = d
                            print(f"  ✓ 找到 info API: {url}", flush=True)
                            print(f"  data keys: {list(d.keys())[:10]}", flush=True)
                            break
                    except Exception as e:
                        print(f"  解析失败: {e}", flush=True)

            if info_data:
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
                print(f"  名称: {result['info']['name']}", flush=True)
                print(f"  悠悠卖价: {result['info']['yyyp_sell_price']}", flush=True)
            else:
                result["errors"].append("info API 未找到或无数据")
                print(f"  ✗ 未找到 info API 或无数据", flush=True)

            # 3. 点击 K 线图
            print("\n[3] 点击 K 线图...", flush=True)
            clicked = page.evaluate("""() => {
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    if (btn.textContent.trim() === 'K线图') {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }""")
            print(f"  点击结果: {clicked}", flush=True)
            page.wait_for_timeout(3000)

            # 4. 切换平台到悠悠有品
            print("\n[4] 切换平台到悠悠有品...", flush=True)
            select_info = page.evaluate("""() => {
                const selects = document.querySelectorAll('select');
                for (const sel of selects) {
                    const options = Array.from(sel.options).map(o => ({text: o.text, value: o.value}));
                    if (options.some(o => o.text === '悠悠有品')) {
                        const yyyp = options.find(o => o.text === '悠悠有品');
                        return {value: yyyp.value, options: options};
                    }
                }
                return null;
            }""")
            print(f"  select 信息: {select_info}", flush=True)
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

            # 5. 切换日线
            print("\n[5] 切换日线...", flush=True)
            chart_before = chart_call_count
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
            print(f"  chartAll 调用数: {chart_call_count} (新增 {chart_call_count - chart_before})", flush=True)

            # 提取日线数据 - 取第一次 chartAll 响应
            chart_url = "https://csqaq.com/proxies/api/v1/info/simple/chartAll"
            if chart_url in all_api_data and all_api_data[chart_url]:
                try:
                    parsed = json.loads(all_api_data[chart_url][0]["body"])
                    if parsed.get("code") == 200:
                        arr = parsed.get("data", [])
                        if isinstance(arr, list) and len(arr) > 0:
                            result["chart_daily"] = {
                                "count": len(arr),
                                "first": arr[0],
                                "last": arr[-1],
                            }
                            print(f"  ✓ 日线: {len(arr)} 条", flush=True)
                except Exception as e:
                    print(f"  日线解析失败: {e}", flush=True)

            # 6. 切换 1 小时
            print("\n[6] 切换 1 小时...", flush=True)
            chart_before = chart_call_count
            # 尝试多种文本
            clicked_1h = page.evaluate("""() => {
                const targets = ['1小时', '1H', '1h', '1小时线'];
                const els = document.querySelectorAll('span, div, a, button, li');
                for (const target of targets) {
                    for (const el of els) {
                        if (el.textContent.trim() === target && el.offsetParent !== null) {
                            el.click();
                            return target;
                        }
                    }
                }
                return false;
            }""")
            print(f"  点击: {clicked_1h}", flush=True)
            page.wait_for_timeout(4000)
            print(f"  chartAll 调用数: {chart_call_count} (新增 {chart_call_count - chart_before})", flush=True)

            # 提取 1 小时数据 - 取第二次 chartAll 响应
            if chart_url in all_api_data and len(all_api_data[chart_url]) >= 2:
                try:
                    parsed = json.loads(all_api_data[chart_url][-1]["body"])
                    if parsed.get("code") == 200:
                        arr = parsed.get("data", [])
                        if isinstance(arr, list) and len(arr) > 0:
                            result["chart_1h"] = {
                                "count": len(arr),
                                "first": arr[0],
                                "last": arr[-1],
                            }
                            print(f"  ✓ 1小时: {len(arr)} 条", flush=True)
                except Exception as e:
                    result["errors"].append(f"1小时解析失败: {e}")

            # 7. 点击筹码分布图
            print("\n[7] 点击筹码分布图...", flush=True)
            # 尝试多种选择器
            chip_clicked = page.evaluate("""() => {
                // 尝试 class 选择器
                const chipEl = document.querySelector('.chip_tag___2aXfK');
                if (chipEl) { chipEl.click(); return 'class'; }
                // 尝试文本匹配
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
            page.wait_for_timeout(5000)
            print(f"  chipData API 是否调用: {'https://csqaq.com/proxies/api/v1/info/chipData' in all_api_data}", flush=True)

            # 如果没找到，尝试通过 K 线图下方的标签切换
            if not chip_clicked or 'https://csqaq.com/proxies/api/v1/info/chipData' not in all_api_data:
                print("  尝试查找所有可点击的标签...", flush=True)
                tags = page.evaluate("""() => {
                    const results = [];
                    document.querySelectorAll('span, div, a, button, li, p').forEach(el => {
                        const text = el.textContent.trim();
                        if (text.length > 0 && text.length < 20 && el.offsetParent !== null) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                results.push({text: text, tag: el.tagName, class: (el.className || '').toString().substring(0, 50)});
                            }
                        }
                    });
                    return results.slice(0, 50);
                }""")
                print(f"  可见标签: {[t['text'] for t in tags]}", flush=True)

                # 尝试点击包含"筹码"的元素
                chip_clicked2 = page.evaluate("""() => {
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
                print(f"  二次点击: {chip_clicked2}", flush=True)
                page.wait_for_timeout(5000)

            # 提取筹码分布图数据
            chip_url = "https://csqaq.com/proxies/api/v1/info/chipData"
            if chip_url in all_api_data and all_api_data[chip_url]:
                try:
                    parsed = json.loads(all_api_data[chip_url][-1]["body"])
                    if parsed.get("code") == 200 and parsed.get("data"):
                        d = parsed["data"]
                        result["chip_data"] = {
                            "fields": list(d.keys()),
                            "date_count": len(d.get("date", [])),
                            "first_date": d.get("date", [None])[0],
                            "last_date": d.get("date", [None])[-1],
                            "sample_low": d.get("low", [])[:3],
                            "sample_high": d.get("high", [])[:3],
                            "sample_volume": d.get("volume", [])[:3],
                        }
                        print(f"  ✓ 筹码分布: {result['chip_data']['date_count']} 天", flush=True)
                except Exception as e:
                    result["errors"].append(f"筹码分布解析失败: {e}")

            browser.close()

    except Exception as e:
        result["errors"].append(f"Playwright 运行失败: {type(e).__name__}: {e}")
        print(f"\n[FATAL] {type(e).__name__}: {e}", flush=True)

    # 保存结果
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[8] 结果已保存: {RESULT_FILE}", flush=True)

    # 汇总
    print("\n" + "=" * 60, flush=True)
    print("  测试汇总", flush=True)
    print("=" * 60, flush=True)
    print(f"  基本信息: {'✓' if result['info'] else '✗'}", flush=True)
    print(f"  日线数据: {'✓' if result['chart_daily'] else '✗'}", flush=True)
    print(f"  1小时数据: {'✓' if result['chart_1h'] else '✗'}", flush=True)
    print(f"  筹码分布: {'✓' if result['chip_data'] else '✗'}", flush=True)
    print(f"  错误数: {len(result['errors'])}", flush=True)
    for err in result["errors"]:
        print(f"    - {err}", flush=True)


if __name__ == "__main__":
    main()
