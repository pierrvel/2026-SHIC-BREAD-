"""Public-site navigation and MJPEG checks using a local synthetic read-only origin."""
import os
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

base = os.getenv('BREAD_TEST_URL', 'http://127.0.0.1:15173')
stream = os.environ['BREAD_TEST_STREAM_URL']
parts = urlsplit(stream)
health_url = f'{parts.scheme}://{parts.netloc}/api/health'
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.getenv('BREAD_CHROMIUM_PATH', '/usr/bin/chromium'), headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 1050})
    page = context.new_page()
    errors, requests, closed = [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    page.on('requestfailed', lambda request: closed.append(request.url))
    page.goto(base)
    expect(page.get_by_role('heading', name='우리 학교 빵 자판기, 한눈에 보기 🥐')).to_be_visible()
    expect(page.get_by_role('button', name='관리자', exact=True)).to_have_count(0)
    expect(page.get_by_role('button', name='재고 있는 칸', exact=True)).to_have_count(0)
    expect(page.get_by_text('선택한 위치에서 빵 직접 확인', exact=False)).to_be_visible()
    page.goto(base + '/#admin')
    expect(page.get_by_role('heading', name='자판기 슬롯 지도', exact=True)).to_be_visible()
    assert not any('firebase' in url or 'googleapis' in url or '/api/status' in url for url in requests), 'public site must not connect to inventory services'
    assert not any('/stream.mjpg' in url for url in requests), 'map must not open a stream'
    page.get_by_role('button', name='B2 5번 칸 선택', exact=True).click()
    expect(page.locator('.selected-number')).to_have_text('B2')
    page.get_by_role('button', name='실시간 카메라에서 확인 →', exact=True).click()
    expect(page.locator('.info-badge')).to_contain_text('B2')
    expect(page.get_by_text('현재 실제 카메라 영상은 재생되지 않습니다.', exact=True)).to_be_visible()
    page.get_by_role('button', name='⚙ 영상 연결 설정', exact=True).click()
    field = page.get_by_label('MJPEG 스트리밍 HTTPS 주소', exact=True)
    field.fill('https://invalid-user:invalid-password@example.org/stream.mjpg')
    page.get_by_role('button', name='설정 저장', exact=True).click()
    expect(page.locator('dialog').get_by_role('alert')).to_contain_text('HTTPS 영상 주소')
    field.fill(stream)
    page.get_by_role('button', name='설정 저장', exact=True).click()
    page.wait_for_function('document.querySelector(".live-img")?.naturalWidth===1920', timeout=10000)
    expect(page.get_by_text('영상 표시 중 · 1920 × 1080', exact=True)).to_be_visible()
    expect(page.get_by_text('합성 테스트 영상', exact=False)).to_be_visible()
    page.screenshot(path='/tmp/bread-student-camera.png', full_page=True)
    page.get_by_role('button', name='⛶ 전체 화면', exact=True).click()
    page.wait_for_function('document.fullscreenElement !== null')
    page.evaluate('document.exitFullscreen()')
    page.get_by_role('button', name='슬롯 지도', exact=True).click()
    expect(page.locator('.live-img')).to_have_count(0)
    deadline = time.monotonic() + 5
    while page.request.get(health_url).json()['clients'] and time.monotonic() < deadline:
        page.wait_for_timeout(100)
    assert page.request.get(health_url).json()['clients'] == 0, 'leaving the camera must close its server connection'
    page.get_by_role('button', name='실시간 카메라', exact=True).click()
    page.wait_for_function('document.querySelector(".live-img")?.naturalWidth===1920')
    page.reload(wait_until='domcontentloaded')
    page.wait_for_function('document.querySelector(".live-img")?.naturalWidth===1920')
    for width in (375, 320):
        page.set_viewport_size({'width': width, 'height': 1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'camera overflow at {width}'
    page.route('**/stream.mjpg', lambda route: route.abort())
    page.get_by_role('button', name='↻ 다시 연결', exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('영상 주소 또는 파이 연결 상태')
    page.unroute('**/stream.mjpg')
    page.get_by_role('button', name='↻ 다시 연결', exact=True).click()
    page.wait_for_function('document.querySelector(".live-img")?.naturalWidth===1920')
    assert not errors, errors
    print('PASS supplied design: slot selection, isolated camera route, rejected credentials, FHD MJPEG, persisted URL, stream cancellation, fullscreen, mobile and recovery')
    browser.close()
