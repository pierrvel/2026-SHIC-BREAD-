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
