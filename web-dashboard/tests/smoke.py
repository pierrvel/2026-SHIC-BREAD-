"""Basic checks for the current streaming-only storefront, no camera required."""
import os
from playwright.sync_api import expect, sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.getenv('BREAD_CHROMIUM_PATH', '/usr/bin/chromium'), headless=True)
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.route('https://fonts.googleapis.com/**', lambda r: r.abort())
    page.goto(os.getenv('BREAD_TEST_URL', 'http://127.0.0.1:5173'))
    expect(page).to_have_title('재빵소')
    expect(page.get_by_role('heading', name='빵 남았나, 창문으로 보고 가요')).to_be_visible()
    expect(page.locator('#glass')).to_have_attribute('data-state', 'idle')
    page.locator('#shadeBtn').click()
    page.get_by_label('MJPEG 스트리밍 HTTPS 주소').fill('https://user:password@example.org/')
    page.get_by_label('MJPEG 스트리밍 HTTPS 주소').press('Enter')
    expect(page.locator('#validation')).to_contain_text('HTTPS 주소')
    page.locator('#closeDialog').click()
    for width in (1440, 375, 320):
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors, errors
    print('PASS Jaebbangso branding, idle camera, keyboard validation, desktop/mobile layouts')
    browser.close()
