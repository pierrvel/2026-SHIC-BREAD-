"""Camera preview browser check against an explicitly --sample server."""
import os

from playwright.sync_api import expect, sync_playwright

base = os.environ['BREAD_TEST_URL']
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.getenv('BREAD_CHROMIUM_PATH', '/usr/bin/chromium'), headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    errors, external = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: external.append(request.url) if not request.url.startswith(base + '/') else None)
    page.goto(base, wait_until='domcontentloaded')
    assert page.request.get(base + '/api/health').json()['sample'], 'Only test explicit synthetic mode'
    expect(page.locator('#source')).to_contain_text('합성 테스트 영상')
    expect(page.locator('#settings')).to_contain_text('JPEG 품질')
    expect(page.locator('#status')).to_have_attribute('data-live', 'true')
    # Decode actual browser image pixels: HTTP/health success alone is insufficient.
    page.evaluate('''() => {
        const c=document.createElement('canvas'); c.width=320;c.height=240;
        window.previewPixels=()=>{c.getContext('2d').drawImage(document.querySelector('#video'),0,0,320,240);return c.toDataURL()};
        window.initialPixels=previewPixels();
    }''')
    page.wait_for_function('previewPixels() !== initialPixels', timeout=5000)
    page.get_by_role('button', name='좌우 반전').click()
    expect(page.locator('#video')).to_have_class('mirror')
    page.get_by_role('button', name='전체 화면').click()
    page.wait_for_function('document.fullscreenElement !== null')
    page.evaluate('document.exitFullscreen()')
    page.wait_for_function('document.fullscreenElement === null')
    page.get_by_role('button', name='다시 연결').click()
    expect(page.locator('#status')).to_have_attribute('data-live', 'true')
    other = browser.new_page()
    other.goto(base, wait_until='domcontentloaded')
    expect(other.get_by_role('button', name='설정 적용')).to_be_enabled()
    other.get_by_label('목표 FPS', exact=True).fill('45')
    # UI updates must reach the Python producer and both browsers, including
    # newly decoded JPEG dimensions rather than just optimistic form values.
    page.get_by_label('해상도', exact=True).select_option('1920x1080')
    page.get_by_label('목표 FPS', exact=True).fill('60')
    page.get_by_label('JPEG 화질', exact=False).fill('85')
    page.get_by_label('노이즈 제거', exact=True).check()
    page.get_by_role('button', name='설정 적용').click()
    expect(page.locator('#control-status')).to_contain_text('설정을 적용했습니다', timeout=15000)
    expect(page.get_by_role('button', name='설정 적용')).to_be_enabled()
    h = page.request.get(base + '/api/health').json()
    assert (h['requested_width'], h['requested_height'], h['target_fps'], h['quality'], h['denoise']) == (1920, 1080, 60, 85, True)
    page.wait_for_function('document.querySelector("#video").naturalWidth===1920 && document.querySelector("#video").naturalHeight===1080')
    other.wait_for_function('document.querySelector("#video").naturalWidth===1920')
    expect(other.locator('#control-status')).to_contain_text('다른 화면에서 설정이 변경됐습니다')
    expect(other.get_by_label('목표 FPS', exact=True)).to_have_value('45')
    other.get_by_role('button', name='설정 적용').click()
    expect(other.locator('#control-status')).to_contain_text('현재 설정 불러오기')
    other.get_by_role('button', name='현재 설정 불러오기').click()
    expect(other.get_by_label('목표 FPS', exact=True)).to_have_value('60')
    other.close()
    # Quality/noise controls should also apply without changing camera dimensions.
    page.get_by_label('JPEG 화질', exact=False).fill('90')
    page.get_by_label('노이즈 제거', exact=True).uncheck()
    page.get_by_role('button', name='설정 적용').click()
    expect(page.locator('#control-status')).to_contain_text('설정을 적용했습니다', timeout=15000)
    expect(page.locator('#settings')).to_contain_text('노이즈 제거 꺼짐')
    page.set_viewport_size({'width': 375, 'height': 850})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path='/tmp/school-bread-camera-mobile.png')
    page.route('**/api/health', lambda route: route.abort())
    expect(page.locator('#status')).to_contain_text('서버 연결 끊김')
    expect(page.locator('#status')).to_have_attribute('data-live', 'false')
    page.unroute('**/api/health')
    expect(page.locator('#status')).to_have_attribute('data-live', 'true')
    assert not errors, errors
    assert not external, external
    print('PASS browser decodes changing MJPEG frames; sample label, flip/reconnect, mobile layout and offline recovery work without external requests')
    browser.close()
