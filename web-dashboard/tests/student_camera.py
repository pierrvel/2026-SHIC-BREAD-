"""Jaebbangso storefront with a real MJPEG stream from the synthetic Pi source."""
import os
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

base = os.getenv('BREAD_TEST_URL', 'http://127.0.0.1:14190')
stream = os.environ['BREAD_TEST_STREAM_URL']
parts = urlsplit(stream)
health_url = f'{parts.scheme}://{parts.netloc}/api/health'

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.getenv('BREAD_CHROMIUM_PATH', '/usr/bin/chromium'), headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 1100})
    context.route('https://fonts.googleapis.com/**', lambda r: r.abort())
    page = context.new_page()
    errors, requests = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    def state(value):
        expect(page.locator('#glass')).to_have_attribute('data-state', value, timeout=12000)
    def no_clients():
        deadline = time.monotonic() + 5
        while page.request.get(health_url).json()['clients'] and time.monotonic() < deadline:
            page.wait_for_timeout(100)
        assert page.request.get(health_url).json()['clients'] == 0, 'stream must be cancelled on Pi too'
    def visibility(hidden):
        page.evaluate('''hidden => {
          Object.defineProperty(document, 'hidden', {configurable:true, get:() => hidden});
          document.dispatchEvent(new Event('visibilitychange'));
        }''', hidden)
    page.goto(base)
    expect(page).to_have_title('재빵소')
    expect(page.get_by_role('heading', name='빵 남았나, 창문으로 보고 가요')).to_be_visible()
    state('idle')
    expect(page.locator('#signTitle')).to_have_text('개업 준비중')
    assert not any('/stream.mjpg' in url for url in requests)
    expect(page.locator('.slot-card')).to_have_count(0)
    page.screenshot(path='/tmp/jaebbangso-desktop.png', full_page=True)
    page.locator('#shadeBtn').click()
    field = page.get_by_label('MJPEG 스트리밍 HTTPS 주소', exact=True)
    for invalid in ['https://user:password@example.org/stream.mjpg', 'javascript:alert(1)', 'http://192.168.0.23:8081/stream.mjpg']:
        field.fill(invalid)
        page.get_by_role('button', name='저장하고 연결', exact=True).click()
        expect(page.locator('#validation')).to_contain_text('HTTPS 주소')
    field.fill(stream)
    page.get_by_role('button', name='저장하고 연결', exact=True).click()
    state('live')
    page.wait_for_function('document.querySelector("#liveImg").naturalWidth === 1920')
    expect(page.locator('#sampleBadge')).to_be_visible()
    expect(page.locator('#signTitle')).to_have_text('테스트중')
    assert page.locator('#glass').evaluate('e => e.style.aspectRatio') == '1920 / 1080'
    page.locator('[data-open-settings]').click()
    expect(page.locator('#cameraDetails')).to_contain_text('1920 × 1080')
    page.locator('#closeDialog').click()
    page.get_by_role('button', name='잠깐 멈추기', exact=True).click()
    state('paused'); no_clients()
    visibility(True); visibility(False)
    state('paused')  # manual pause must survive tab changes
    page.get_by_role('button', name='다시 보기', exact=True).first.click()
    state('live')
    visibility(True); state('paused'); no_clients()
    visibility(False); state('live')
    page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide', {persisted:true}))")
    state('paused'); no_clients()
    page.evaluate("dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}))")
    state('live')
    page.locator('#fullscreenBtn').click()
    page.wait_for_function('document.fullscreenElement !== null')
    expect(page.locator('#fullscreenLabel')).to_have_text('작게 보기')
    page.evaluate('document.exitFullscreen()')
    for width in (375, 320):
        page.set_viewport_size({'width': width, 'height': 1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'overflow at {width}'
    page.screenshot(path='/tmp/jaebbangso-mobile.png', full_page=True)
    page.reload(wait_until='domcontentloaded'); state('live')
    page.locator('[data-open-settings]').click()
    field.fill('https://offline.invalid/?action=stream')
    page.route('https://offline.invalid/**', lambda r: r.abort())
    page.get_by_role('button', name='저장하고 연결', exact=True).click()
    state('error')
    expect(page.locator('#signTitle')).to_have_text('잠깐 쉬어요')
    no_clients()  # a previous naturalWidth must not mark the new URL live
    page.locator('[data-open-settings]').click(); field.fill(stream)
    page.get_by_role('button', name='저장하고 연결', exact=True).click(); state('live')
    stale = page.request.get(health_url).json()
    stale['live'] = False
    page.route(health_url, lambda r: r.fulfill(json=stale, headers={'Access-Control-Allow-Origin': '*'}))
    state('error'); no_clients()
    expect(page.locator('#connectionNotice')).to_contain_text('새 영상이 도착하지')
    page.unroute(health_url)
    page.locator('#refreshBtn').click(); state('live')
    # A capture reconfiguration should reconnect without a student changing settings.
    version = page.request.get(health_url).json(); version['stream_version'] += 1
    page.route(health_url, lambda r: r.fulfill(json=version, headers={'Access-Control-Allow-Origin': '*'}))
    before = sum('/stream.mjpg' in u for u in requests)
    deadline = time.monotonic() + 6
    while sum('/stream.mjpg' in u for u in requests) == before and time.monotonic() < deadline:
        page.wait_for_timeout(100)
    assert sum('/stream.mjpg' in u for u in requests) > before
    state('live'); page.unroute(health_url)
    page.locator('[data-open-settings]').click(); page.locator('#clearBtn').click()
    state('idle'); no_clients()
    page.reload(); state('idle')
    for key in ['bread-salpim.camera.v1', 'breadCamStudentDashboard.v2']:
        page.evaluate('([key,url]) => { localStorage.clear(); localStorage.setItem(key, key.includes("Dashboard") ? JSON.stringify({url}) : url); }', [key, stream])
        page.reload(wait_until='domcontentloaded'); state('live')
        page.locator('[data-open-settings]').click(); page.locator('#clearBtn').click(); state('idle')
        page.reload(); state('idle')
    assert not any('firebaseio' in u or 'firebasedatabase' in u or '/api/status' in u for u in requests)
    assert not errors, errors
    print('PASS Jaebbangso: FHD MJPEG, truthful status, pause/cancellation, visibility/BFCache, fullscreen, mobile, stale source, camera reconfiguration, legacy settings and reset')
    browser.close()
